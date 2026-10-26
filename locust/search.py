"""HW6 search-only workload: identical settings for direct-task and ALB comparisons."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import random
from urllib.parse import quote

import gevent
import psutil
from locust import FastHttpUser, constant, events, task

QUERIES = ("Electro", "Books", "Home", "Sports", "Clothing", "Alpha", "Camera")


class SearchUser(FastHttpUser):
    wait_time = constant(0)

    @task
    def search(self):
        with self.client.get("/products/search?q=" + quote(random.choice(QUERIES)),
                             name="GET /products/search?q=...",
                             catch_response=True, timeout=10) as response:
            if response.status_code != 200:
                response.failure(f"Expected 200, got {response.status_code}")
                return
            try:
                result = response.json()
                count = result["total_found"]
                if (type(count) is not int or not isinstance(result["products"], list)
                        or count != len(result["products"]) or not 0 <= count <= 20
                        or not isinstance(result["search_time"], str)):
                    response.failure("Invalid search response")
            except (ValueError, KeyError, TypeError):
                response.failure("Invalid search JSON")


def utc():
    return datetime.now(timezone.utc).isoformat()


@events.test_start.add_listener
def started(environment, **kwargs):
    folder = Path(os.getenv("RESULT_DIR", "results/hw6"))
    folder.mkdir(parents=True, exist_ok=True)
    run = os.getenv("RUN_NAME", "search")
    environment.hw6_path = folder / f"{run}_window.json"
    environment.hw6_window = {"start_utc": utc(), "host": environment.host,
                              "queries": QUERIES, "wait_seconds": 0,
                              "warmup_reset": False,
                              "load_generator": os.getenv("LOAD_GENERATOR", "unspecified")}
    environment.hw6_path.write_text(json.dumps(environment.hw6_window, indent=2) + "\n")

    def monitor():
        process = psutil.Process()
        process.cpu_percent()
        with (folder / f"{run}_generator.csv").open("w") as stream:
            stream.write("utc,process_cpu_percent,rss_bytes\n")
            while environment.runner.state not in {"stopped", "stopping", "cleanup"}:
                stream.write(f"{utc()},{process.cpu_percent()},{process.memory_info().rss}\n")
                stream.flush()
                gevent.sleep(1)

    gevent.spawn(monitor)


@events.test_stop.add_listener
def stopped(environment, **kwargs):
    if hasattr(environment, "hw6_window"):
        environment.hw6_window["end_utc"] = utc()
        environment.hw6_path.write_text(json.dumps(environment.hw6_window, indent=2) + "\n")
