"""Identical Product workloads for both clients; no application logic lives here."""
import csv
import os
import random
import time
from pathlib import Path

import gevent
import psutil
from locust import HttpUser, FastHttpUser, between, constant, events, task

MODE = os.getenv("WORKLOAD", "performance")
if MODE not in {"performance", "errors"}:
    raise ValueError("WORKLOAD must be performance or errors")
STRESS = os.getenv("STRESS", "false") == "true"
WARMUP = int(os.getenv("WARMUP_SECONDS", "20"))


class ProductTasks:
    wait_time = constant(0) if STRESS else between(0.05, 0.15)

    @task
    def product_request(self):
        choice = random.randrange(100)
        product_id = random.randint(1, 1000)
        if MODE == "errors" and choice >= 98:
            if choice == 98:
                with self.client.get("/products/1001", name="GET missing product (expected 404)", catch_response=True, timeout=10) as response:
                    self.check(response, 404)
            else:
                with self.client.post("/products/1/details", json={"product_id": 1}, name="POST invalid product (expected 400)", catch_response=True, timeout=10) as response:
                    self.check(response, 400)
        elif choice < (88 if MODE == "errors" else 90):
            with self.client.get(f"/products/{product_id}", name="GET /products/{id}", catch_response=True, timeout=10) as response:
                self.check(response, 200, product_id)
        else:
            payload = {"product_id": product_id, "sku": f"SKU-{product_id:04d}", "manufacturer": "HW5 Locust", "category_id": 1, "weight": 100, "some_other_id": 1}
            with self.client.post(f"/products/{product_id}/details", json=payload, name="POST /products/{id}/details", catch_response=True, timeout=10) as response:
                self.check(response, 204)

    @staticmethod
    def check(response, expected, product_id=None):
        if response.status_code != expected:
            response.failure(f"Expected {expected}, got {response.status_code}")
        elif expected == 204 and response.content:
            response.failure("204 response contained a body")
        elif product_id is not None:
            try:
                if response.json().get("product_id") != product_id:
                    response.failure("GET returned the wrong product")
                else:
                    response.success()
            except (ValueError, AttributeError):
                response.failure("GET returned invalid Product JSON")
        else:
            response.success()


class ProductHttpUser(ProductTasks, HttpUser):
    tasks = [ProductTasks.product_request]


class ProductFastHttpUser(ProductTasks, FastHttpUser):
    tasks = [ProductTasks.product_request]


@events.test_start.add_listener
def on_start(environment, **kwargs):
    started = time.monotonic()
    process = psutil.Process()
    process.cpu_percent()
    result_dir = Path(os.getenv("RESULT_DIR", "/tmp"))
    result_dir.mkdir(parents=True, exist_ok=True)
    run_name = os.getenv("RUN_NAME", "smoke")

    def sample_cpu():
        with (result_dir / f"{run_name}_cpu.csv").open("w", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["unix_time", "elapsed_seconds", "phase", "process_cpu_percent", "rss_bytes"])
            while environment.runner.state not in {"stopped", "stopping", "cleanup"}:
                elapsed = time.monotonic() - started
                writer.writerow([time.time(), elapsed, "warmup" if elapsed < WARMUP else "measurement", process.cpu_percent(), process.memory_info().rss])
                stream.flush()
                gevent.sleep(1)

    def reset_after_warmup():
        gevent.sleep(WARMUP)
        if environment.runner.state not in {"stopped", "stopping", "cleanup"}:
            environment.stats.reset_all()
            print(f"MEASUREMENT START: {run_name}; warmup={WARMUP}s", flush=True)

    gevent.spawn(sample_cpu)
    gevent.spawn(reset_after_warmup)

# The shape exists only for stress runs, so it cannot alter comparisons.
if os.getenv("STRESS_SHAPE", "false") == "true":
    from locust import LoadTestShape

    class ProductStressShape(LoadTestShape):
        # One minute per level, including the short ramp to that level.
        levels = [50, 100, 200, 400, 700, 1000]

        def tick(self):
            stage = int(self.get_run_time() // 60)
            if stage >= len(self.levels):
                return None
            return self.levels[stage], 50
