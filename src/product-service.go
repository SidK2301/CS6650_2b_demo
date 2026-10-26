package main

import (
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"os"
	"strconv"
	"strings"
	"sync"
	"time"
	"unicode/utf8"

	"github.com/gin-gonic/gin"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

type Product struct {
	ProductID    int32  `json:"product_id"`
	SKU          string `json:"sku"`
	Manufacturer string `json:"manufacturer"`
	CategoryID   int32  `json:"category_id"`
	Weight       int32  `json:"weight"`
	SomeOtherID  int32  `json:"some_other_id"`
}

type apiError struct {
	Error   string `json:"error"`
	Message string `json:"message"`
	Details string `json:"details,omitempty"`
}

type application struct {
	products   sync.Map         // int32 product IDs mapped to immutable Product values.
	names      map[int32]string // Generated names are immutable after startup; not part of the Product API schema.
	categories map[int32]string
	registry   *prometheus.Registry
	requests   *prometheus.CounterVec
	errors     *prometheus.CounterVec
	duration   *prometheus.HistogramVec
	logger     *slog.Logger
	faults     bool
}

func newApplication(logOutput io.Writer, faults bool) *application {
	a := &application{names: make(map[int32]string, 100000), categories: map[int32]string{1: "Electronics", 2: "Books", 3: "Home", 4: "Sports", 5: "Clothing"}, registry: prometheus.NewRegistry(), logger: slog.New(slog.NewJSONHandler(logOutput, nil)), faults: faults}
	brands := []string{"Alpha", "Beta", "Gamma", "Delta", "Omega"}
	items := []string{"Camera", "Notebook", "Lamp", "Ball", "Jacket"}
	for id := int32(1); id <= 100000; id++ {
		index := int(id - 1)
		brand := brands[(index/len(items))%len(brands)]
		a.names[id] = fmt.Sprintf("%s %s %d", items[index%len(items)], brand, id)
		a.products.Store(id, Product{ProductID: id, SKU: fmt.Sprintf("SKU-%06d", id), Manufacturer: brand, CategoryID: int32(index%len(a.categories)) + 1, Weight: 100, SomeOtherID: 1})
	}
	labels := []string{"route", "method", "status"}
	a.requests = prometheus.NewCounterVec(prometheus.CounterOpts{Name: "requests_total", Help: "Business HTTP requests."}, labels)
	a.errors = prometheus.NewCounterVec(prometheus.CounterOpts{Name: "errors_total", Help: "Business non-2xx responses."}, labels)
	a.duration = prometheus.NewHistogramVec(prometheus.HistogramOpts{Name: "request_duration_seconds", Help: "Server HTTP duration in seconds.", Buckets: []float64{.0001, .00025, .0005, .001, .0025, .005, .01, .025, .05, .1, .25, 1, 2.5, 5, 10}}, labels)
	a.registry.MustRegister(a.requests, a.errors, a.duration)
	return a
}

func fail(c *gin.Context, status int, code, message string) {
	c.AbortWithStatusJSON(status, apiError{Error: code, Message: message})
}

func invalidField(c *gin.Context, details string) {
	c.AbortWithStatusJSON(400, apiError{Error: "INVALID_INPUT", Message: "Invalid product data", Details: details})
}

func (a *application) observe() gin.HandlerFunc {
	return func(c *gin.Context) {
		started := time.Now()
		c.Next()
		route := c.FullPath()
		if route == "" {
			route = "unmatched"
		}
		status := c.Writer.Status()
		elapsed := time.Since(started)
		if route != "/metrics" && route != "/health" {
			labels := []string{route, c.Request.Method, strconv.Itoa(status)}
			a.requests.WithLabelValues(labels...).Inc()
			if status < 200 || status >= 300 {
				a.errors.WithLabelValues(labels...).Inc()
			}
			a.duration.WithLabelValues(labels...).Observe(elapsed.Seconds())
		}
		attributes := []any{"endpoint", route, "method", c.Request.Method, "status", status, "duration_ms", float64(elapsed) / float64(time.Millisecond)}
		if checked, exists := c.Get("checked"); exists {
			attributes = append(attributes, "checked", checked)
		}
		a.logger.Info("request", attributes...)
	}
}

func (a *application) router() *gin.Engine {
	r := gin.New()
	r.RedirectTrailingSlash = false
	r.Use(a.observe())
	r.Use(func(c *gin.Context) {
		defer func() {
			if recovered := recover(); recovered != nil {
				if recovered == http.ErrAbortHandler {
					panic(recovered)
				}
				a.logger.Error("panic", "value", recovered, "endpoint", c.FullPath())
				fail(c, 500, "INTERNAL_ERROR", "Internal server error")
			}
		}()
		c.Next()
	})
	r.GET("/health", func(c *gin.Context) { c.JSON(200, gin.H{"status": "ok"}) })
	r.GET("/metrics", gin.WrapH(promhttp.HandlerFor(a.registry, promhttp.HandlerOpts{})))
	for _, prefix := range []string{"", "/v1"} {
		r.GET(prefix+"/products/search", a.searchProducts)
		r.GET(prefix+"/products/:productId", a.getProduct)
		r.POST(prefix+"/products/:productId/details", a.updateProduct)
	}
	r.NoRoute(func(c *gin.Context) { fail(c, 404, "NOT_FOUND", "Route not found") })
	return r
}

type searchResponse struct {
	Products   []Product `json:"products"`
	TotalFound int       `json:"total_found"`
	SearchTime string    `json:"search_time"`
}

func (a *application) searchProducts(c *gin.Context) {
	a.inject(c)
	started := time.Now()
	query, exists := c.GetQuery("q")
	if !exists || !utf8.ValidString(query) || utf8.RuneCountInString(query) < 1 || utf8.RuneCountInString(query) > 100 {
		fail(c, 400, "INVALID_INPUT", "q must contain 1–100 characters")
		return
	}
	query = strings.ToLower(query)
	products := make([]Product, 0, 20)
	checked := 0
	a.products.Range(func(key, value any) bool {
		p := value.(Product)
		checked++
		matches := strings.Contains(strings.ToLower(a.names[key.(int32)]), query) || strings.Contains(strings.ToLower(a.categories[p.CategoryID]), query)
		if matches && len(products) < 20 {
			products = append(products, p)
		}
		// Bound examined products, independent of how many match or are returned.
		return checked < 100
	})
	c.Set("checked", checked)
	c.JSON(200, searchResponse{Products: products, TotalFound: len(products), SearchTime: time.Since(started).String()})
}

func parseID(c *gin.Context) (int32, bool) {
	n, err := strconv.ParseInt(c.Param("productId"), 10, 32)
	return int32(n), err == nil && n >= 1
}

func (a *application) inject(c *gin.Context) {
	if a.faults && c.GetHeader("X-Fault-Inject") == "500" {
		panic("controlled local verification fault")
	}
}

func (a *application) getProduct(c *gin.Context) {
	a.inject(c)
	id, ok := parseID(c)
	if !ok {
		fail(c, 404, "NOT_FOUND", "Product not found")
		return
	}
	p, found := a.products.Load(id)
	if !found {
		fail(c, 404, "NOT_FOUND", "Product not found")
		return
	}
	c.JSON(200, p)
}

func (a *application) updateProduct(c *gin.Context) {
	a.inject(c)
	id, ok := parseID(c)
	if !ok {
		fail(c, 400, "INVALID_INPUT", "Product ID must be a positive int32")
		return
	}
	c.Request.Body = http.MaxBytesReader(c.Writer, c.Request.Body, 1<<20)
	var fields map[string]json.RawMessage
	decoder := json.NewDecoder(c.Request.Body)
	if err := decoder.Decode(&fields); err != nil || fields == nil {
		fail(c, 400, "INVALID_INPUT", "Invalid product JSON")
		return
	}
	var extra any
	if err := decoder.Decode(&extra); err != io.EOF {
		fail(c, 400, "INVALID_INPUT", "Expected one JSON object within 1 MiB")
		return
	}
	var p Product
	// Decode exact keys independently: unknown properties cannot override them
	// through encoding/json's case-insensitive struct-field matching.
	for _, field := range []struct {
		name   string
		target any
	}{
		{"product_id", &p.ProductID}, {"sku", &p.SKU},
		{"manufacturer", &p.Manufacturer}, {"category_id", &p.CategoryID},
		{"weight", &p.Weight}, {"some_other_id", &p.SomeOtherID},
	} {
		raw, exists := fields[field.name]
		if !exists || string(raw) == "null" {
			invalidField(c, field.name+" is required and cannot be null")
			return
		}
		if err := json.Unmarshal(raw, field.target); err != nil {
			invalidField(c, field.name+" has an invalid type or is outside int32 range")
			return
		}
	}
	var detail string
	switch {
	case p.ProductID != id:
		detail = "product_id must match the positive path ID"
	case p.CategoryID < 1:
		detail = "category_id must be >= 1"
	case p.Weight < 0:
		detail = "weight must be >= 0"
	case p.SomeOtherID < 1:
		detail = "some_other_id must be >= 1"
	case utf8.RuneCountInString(p.SKU) < 1 || utf8.RuneCountInString(p.SKU) > 100:
		detail = "sku must contain 1–100 characters"
	case utf8.RuneCountInString(p.Manufacturer) < 1 || utf8.RuneCountInString(p.Manufacturer) > 200:
		detail = "manufacturer must contain 1–200 characters"
	}
	if detail != "" {
		invalidField(c, detail)
		return
	}
	// Replace only an existing value, retrying if another update wins first.
	// CompareAndSwap cannot insert an unknown ID, even under concurrent POSTs.
	found := false
	for {
		previous, exists := a.products.Load(id)
		if !exists {
			break
		}
		if a.products.CompareAndSwap(id, previous, p) {
			found = true
			break
		}
	}
	if !found {
		fail(c, 404, "NOT_FOUND", "Product not found")
		return
	}
	c.Status(204)
}

func main() {
	gin.SetMode(gin.ReleaseMode)
	a := newApplication(os.Stdout, os.Getenv("FAULT_INJECTION") == "true")
	server := &http.Server{Addr: ":8080", Handler: a.router(), ReadHeaderTimeout: 5 * time.Second}
	if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		a.logger.Error("server stopped", "error", err)
		os.Exit(1)
	}
}
