package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/url"
	"strings"
	"testing"
	"time"
)

func TestSearchContractAndBound(t *testing.T) {
	var logs bytes.Buffer
	a := newApplication(&logs, true)
	count := 0
	a.products.Range(func(_, _ any) bool { count++; return true })
	if count != 100000 || len(a.names) != 100000 {
		t.Fatalf("startup products=%d names=%d", count, len(a.names))
	}
	// Make every product's name match, so the cap cannot conceal an early exit.
	for id := range a.names {
		a.names[id] = "Science electron microscope Alpha"
	}
	r := a.router()
	for _, query := range []string{"eLeCtRoN", "aLpHa", "absent-term-xyz", "界"} {
		logs.Reset()
		w := request(r, "GET", "/products/search?q="+url.QueryEscape(query), "", false)
		var result searchResponse
		if w.Code != 200 || json.Unmarshal(w.Body.Bytes(), &result) != nil {
			t.Fatalf("%d %s", w.Code, w.Body.String())
		}
		if result.Products == nil || result.TotalFound != len(result.Products) || len(result.Products) > 20 {
			t.Fatalf("invalid result: %+v", result)
		}
		if query == "eLeCtRoN" || query == "aLpHa" {
			if result.TotalFound != 20 {
				t.Fatalf("match cap: %+v", result)
			}
		} else if result.TotalFound != 0 {
			t.Fatalf("unexpected match: %+v", result)
		}
		if _, err := time.ParseDuration(result.SearchTime); err != nil {
			t.Fatal(err)
		}
		var entry map[string]any
		if err := json.Unmarshal(bytes.TrimSpace(logs.Bytes()), &entry); err != nil || entry["checked"] != float64(100) {
			t.Fatalf("100-product evidence missing: %s", logs.String())
		}
		t.Logf("local handler request evidence: %s", strings.TrimSpace(logs.String()))
	}
	// Force all products into one category to verify category matching independently.
	a.products.Range(func(key, value any) bool {
		p := value.(Product)
		p.CategoryID = 1
		a.products.Store(key, p)
		return true
	})
	w := request(r, "GET", "/v1/products/search?q=eLeCtRoNiCs", "", false)
	var result searchResponse
	if w.Code != 200 || json.Unmarshal(w.Body.Bytes(), &result) != nil || result.TotalFound != 20 {
		t.Fatalf("category: %d %s", w.Code, w.Body.String())
	}
	for _, path := range []string{"/products/search", "/products/search?q=", "/products/search?q=" + strings.Repeat("x", 101), "/products/search?q=%FF"} {
		if w := request(r, "GET", path, "", false); w.Code != 400 {
			t.Fatalf("%s returned %d", path, w.Code)
		}
	}
	if w := request(r, "GET", "/products/search?q="+url.QueryEscape(strings.Repeat("界", 100)), "", false); w.Code != 200 {
		t.Fatalf("unicode boundary: %d", w.Code)
	}
	if w := request(r, "GET", "/products/search?q=Alpha", "", true); w.Code != 500 {
		t.Fatalf("search fault: %d", w.Code)
	}
	w = request(r, "GET", "/metrics", "", false)
	if !strings.Contains(w.Body.String(), `route="/products/search"`) {
		t.Fatal("search metrics missing")
	}
}

func TestUnknownUpdateDoesNotInsert(t *testing.T) {
	a := newApplication(io.Discard, false)
	r := a.router()
	w := request(r, "POST", "/products/100001/details", bodyWith("product_id", 100001), false)
	if w.Code != 404 {
		t.Fatal(w.Code)
	}
	if _, exists := a.products.Load(int32(100001)); exists {
		t.Fatal("unknown update inserted a product")
	}
}

func BenchmarkSearch(b *testing.B) {
	a := newApplication(io.Discard, false)
	r := a.router()
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		w := request(r, "GET", "/products/search?q=Electro", "", false)
		if w.Code != 200 {
			b.Fatal(fmt.Sprintf("search status %d", w.Code))
		}
	}
}
