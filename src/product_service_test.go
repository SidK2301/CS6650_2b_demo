package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"

	"github.com/gin-gonic/gin"
	"github.com/prometheus/client_golang/prometheus/testutil"
)

func validBody(id int) map[string]any {
	return map[string]any{"product_id": id, "sku": "ABC", "manufacturer": "Acme", "category_id": 1, "weight": 100, "some_other_id": 1}
}
func bodyWith(key string, value any) string {
	b := validBody(1)
	b[key] = value
	raw, _ := json.Marshal(b)
	return string(raw)
}
func request(r *gin.Engine, method, path, body string, fault bool) *httptest.ResponseRecorder {
	req := httptest.NewRequest(method, path, strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	if fault {
		req.Header.Set("X-Fault-Inject", "500")
	}
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	return w
}

func TestContract(t *testing.T) {
	gin.SetMode(gin.TestMode)
	good := bodyWith("weight", 0)
	missing := validBody(1)
	delete(missing, "weight")
	raw, _ := json.Marshal(missing)
	cases := []struct {
		name, method, path, body string
		status                   int
		fault                    bool
	}{
		{"get", "GET", "/products/1", "", 200, false},
		{"get trailing slash", "GET", "/products/1/", "", 404, false},
		{"post trailing slash", "POST", "/products/1/details/", good, 404, false},
		{"oversize body", "POST", "/products/1/details", bodyWith("extra", strings.Repeat("x", 1<<20)), 400, false},
		{"uppercase required key", "POST", "/products/1/details", strings.Replace(good, `"sku"`, `"SKU"`, 1), 400, false},
		{"uppercase extra key cannot override", "POST", "/products/1/details", bodyWith("SKU", "ignored"), 204, false},
		{"missing", "GET", "/products/100001", "", 404, false},
		{"bad get", "GET", "/products/abc", "", 404, false},
		{"zero get", "GET", "/products/0", "", 404, false},
		{"negative get", "GET", "/products/-5", "", 404, false},
		{"overflow get", "GET", "/products/2147483648", "", 404, false},
		{"get fault", "GET", "/products/1", "", 500, true},
		{"zero weight", "POST", "/products/1/details", good, 204, false},
		{"v1 update", "POST", "/v1/products/1/details", good, 204, false},
		{"v1 get", "GET", "/v1/products/1", "", 200, false},
		{"bad path", "POST", "/products/abc/details", good, 400, false},
		{"zero path", "POST", "/products/0/details", good, 400, false},
		{"negative path", "POST", "/products/-1/details", good, 400, false},
		{"overflow path", "POST", "/products/2147483648/details", good, 400, false},
		{"malformed", "POST", "/products/1/details", "{", 400, false},
		{"null body", "POST", "/products/1/details", "null", 400, false},
		{"trailing object", "POST", "/products/1/details", good + "{}", 400, false},
		{"missing weight", "POST", "/products/1/details", string(raw), 400, false},
		{"null weight", "POST", "/products/1/details", bodyWith("weight", nil), 400, false},
		{"wrong type", "POST", "/products/1/details", bodyWith("weight", "zero"), 400, false},
		{"negative weight", "POST", "/products/1/details", bodyWith("weight", -1), 400, false},
		{"int overflow", "POST", "/products/1/details", bodyWith("weight", 2147483648), 400, false},
		{"category", "POST", "/products/1/details", bodyWith("category_id", 0), 400, false},
		{"other ID", "POST", "/products/1/details", bodyWith("some_other_id", 0), 400, false},
		{"mismatch", "POST", "/products/1/details", bodyWith("product_id", 2), 400, false},
		{"empty SKU", "POST", "/products/1/details", bodyWith("sku", ""), 400, false},
		{"unicode boundary", "POST", "/products/1/details", bodyWith("sku", strings.Repeat("界", 100)), 204, false},
		{"unicode over", "POST", "/products/1/details", bodyWith("sku", strings.Repeat("界", 101)), 400, false},
		{"empty manufacturer", "POST", "/products/1/details", bodyWith("manufacturer", ""), 400, false},
		{"manufacturer boundary", "POST", "/products/1/details", bodyWith("manufacturer", strings.Repeat("界", 200)), 204, false},
		{"manufacturer over", "POST", "/products/1/details", bodyWith("manufacturer", strings.Repeat("界", 201)), 400, false},
		{"extra fields", "POST", "/products/1/details", bodyWith("extra", "allowed"), 204, false},
		{"unknown update", "POST", "/products/100001/details", bodyWith("product_id", 100001), 404, false},
		{"post fault", "POST", "/products/1/details", good, 500, true},
		{"unknown route", "GET", "/nothing", "", 404, false},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			a := newApplication(io.Discard, true)
			r := a.router()
			w := request(r, tc.method, tc.path, tc.body, tc.fault)
			if w.Code != tc.status {
				t.Fatalf("status %d, want %d: %s", w.Code, tc.status, w.Body.String())
			}
			if tc.status == 204 && w.Body.Len() != 0 {
				t.Fatal("204 body is not empty")
			}
			if tc.status >= 400 {
				var e apiError
				if err := json.Unmarshal(w.Body.Bytes(), &e); err != nil || e.Error == "" || e.Message == "" {
					t.Fatalf("invalid error: %s", w.Body.String())
				}
			}
			if tc.status == 204 {
				g := request(r, "GET", "/products/1", "", false)
				var p Product
				if err := json.Unmarshal(g.Body.Bytes(), &p); err != nil {
					t.Fatal(err)
				}
				var input Product
				_ = json.Unmarshal([]byte(tc.body), &input)
				if p != input {
					t.Fatalf("update not stored: %+v", p)
				}
			}
		})
	}
	// Each required field must independently be present.
	for key := range validBody(1) {
		t.Run("missing "+key, func(t *testing.T) {
			b := validBody(1)
			delete(b, key)
			raw, _ := json.Marshal(b)
			w := request(newApplication(io.Discard, false).router(), "POST", "/products/1/details", string(raw), false)
			if w.Code != 400 {
				t.Fatal(w.Code)
			}
		})
	}
}

func TestFaultObservability(t *testing.T) {
	for _, method := range []string{"GET", "POST"} {
		t.Run(method, func(t *testing.T) {
			var logs bytes.Buffer
			a := newApplication(&logs, true)
			r := a.router()
			path := "/products/1"
			route := "/products/:productId"
			if method == "POST" {
				path += "/details"
				route += "/details"
			}
			w := request(r, method, path, bodyWith("weight", 0), true)
			if w.Code != 500 {
				t.Fatal(w.Code)
			}
			if testutil.ToFloat64(a.requests.WithLabelValues(route, method, "500")) != 1 || testutil.ToFloat64(a.errors.WithLabelValues(route, method, "500")) != 1 {
				t.Fatal("500 metrics missing")
			}
			lines := bytes.Split(bytes.TrimSpace(logs.Bytes()), []byte("\n"))
			if len(lines) != 2 {
				t.Fatalf("want diagnostic and request log, got %s", logs.String())
			}
			var diagnostic, line map[string]any
			if err := json.Unmarshal(lines[0], &diagnostic); err != nil || diagnostic["level"] != "ERROR" || diagnostic["msg"] != "panic" || diagnostic["value"] == nil {
				t.Fatalf("missing panic diagnostic: %s", logs.String())
			}
			if err := json.Unmarshal(lines[1], &line); err != nil || line["status"] != float64(500) || line["msg"] != "request" {
				t.Fatalf("invalid request log: %s", logs.String())
			}
		})
	}
	a := newApplication(io.Discard, false)
	if w := request(a.router(), "GET", "/products/1", "", true); w.Code != 200 {
		t.Fatal("fault header enabled by default")
	}
}

func TestMetricExclusions(t *testing.T) {
	a := newApplication(io.Discard, false)
	r := a.router()
	request(r, "GET", "/health", "", false)
	request(r, "GET", "/metrics", "", false)
	request(r, "GET", "/unknown/123", "", false)
	w := request(r, "GET", "/metrics", "", false)
	if strings.Contains(w.Body.String(), `route="/health"`) || strings.Contains(w.Body.String(), `route="/metrics"`) || !strings.Contains(w.Body.String(), `route="unmatched"`) {
		t.Fatal(w.Body.String())
	}
}

func TestConcurrentReadsUpdates(t *testing.T) {
	a := newApplication(io.Discard, false)
	r := a.router()
	var wg sync.WaitGroup
	for i := 0; i < 20; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			for j := 0; j < 25; j++ {
				body := bodyWith("sku", fmt.Sprintf("worker-%d-%d", i, j))
				w := request(r, "POST", "/products/1/details", body, false)
				if w.Code != 204 {
					t.Errorf("POST: %d", w.Code)
				}
				g := request(r, "GET", "/products/1", "", false)
				var p Product
				if g.Code != 200 || json.Unmarshal(g.Body.Bytes(), &p) != nil || p.ProductID != 1 {
					t.Error("invalid concurrent GET")
				}
			}
		}(i)
	}
	wg.Wait()
}

func TestAbortHandlerPropagates(t *testing.T) {
	a := newApplication(io.Discard, false)
	r := a.router()
	r.GET("/abort-test", func(c *gin.Context) { panic(http.ErrAbortHandler) })
	defer func() {
		if got := recover(); got != http.ErrAbortHandler {
			t.Errorf("abort panic = %v", got)
		}
	}()
	request(r, "GET", "/abort-test", "", false)
}
