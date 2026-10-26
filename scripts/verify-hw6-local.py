#!/usr/bin/env python3
"""Single-user local verification, not the required AWS load tests."""
import datetime
import json
from pathlib import Path
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request


def fetch(path, method="GET", body=None):
    raw = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request("http://127.0.0.1:8080" + path, data=raw,
                                 method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


def main():
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    assert fetch("/health")[0] == 200
    status, raw = fetch("/products/1")
    assert status == 200
    product = json.loads(raw)
    assert fetch("/products/1/details", "POST", product)[0] == 204
    assert json.loads(fetch("/products/1")[1]) == product
    assert fetch("/products/100001")[0] == 404
    assert fetch("/products/search")[0] == 400
    assert fetch("/products/search?q=")[0] == 400
    assert fetch("/products/search?q=" + "x" * 101)[0] == 400
    latencies = []
    samples = []
    for i in range(60):
        query = ("Electro", "aLpHa", "Camera", "not-a-product-xyz")[i % 4]
        before = time.perf_counter()
        status, raw = fetch("/products/search?q=" + urllib.parse.quote(query))
        elapsed = (time.perf_counter() - before) * 1000
        result = json.loads(raw)
        assert status == 200 and 0 <= result["total_found"] <= 20
        assert result["total_found"] == len(result["products"])
        assert isinstance(result["search_time"], str)
        if query == "not-a-product-xyz":
            assert result["products"] == []
        latencies.append(elapsed)
        samples.append({"query": query, "client_ms": elapsed, "total_found": result["total_found"], "search_time": result["search_time"]})
        time.sleep(0.5)
    report = {"scope": "Local Docker, sequential single user; not AWS performance evidence",
              "start_utc": started, "end_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "requests": len(samples), "median_client_ms": statistics.median(latencies),
              "max_client_ms": max(latencies), "samples": samples}
    output = Path(__file__).resolve().parents[1] / "evidence/hw6/phase1-local.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "samples"}, indent=2))


if __name__ == "__main__":
    main()
