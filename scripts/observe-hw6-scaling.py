#!/usr/bin/env python3
"""Read-only timeline of ECS tasks, ALB target health, and per-task request rates."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import time
from urllib.parse import urlencode
from urllib.request import urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-group", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def aws(service, operation, *options):
        command = ["aws", service, operation, "--region", "us-west-2", "--output", "json", *options]
        return json.loads(subprocess.check_output(command, text=True, timeout=30))

    while True:
        snapshot = {"utc": datetime.now(timezone.utc).isoformat()}
        try:
            services = aws("ecs", "describe-services", "--cluster", "cs6650-hw5-product-cluster",
                           "--services", "cs6650-hw5-product")
            if services.get("failures"):
                raise RuntimeError(str(services["failures"]))
            service = services["services"][0]
            snapshot.update(desired=service["desiredCount"], running=service["runningCount"],
                            pending=service["pendingCount"], events=service.get("events", [])[:5],
                            deployments=service.get("deployments", []))
            snapshot["targets"] = aws("elbv2", "describe-target-health", "--target-group-arn", args.target_group)["TargetHealthDescriptions"]
            query = 'sum by(instance)(rate(requests_total{route="/products/search",status="200"}[1m]))'
            with urlopen("http://localhost:9090/api/v1/query?" + urlencode({"query": query}), timeout=10) as response:
                snapshot["request_rates"] = json.load(response)
        except Exception as error:
            snapshot["error"] = str(error)
        with args.output.open("a") as stream:
            stream.write(json.dumps(snapshot) + "\n")
        healthy = sum(t["TargetHealth"]["State"] == "healthy" for t in snapshot.get("targets", []))
        print(f"{snapshot['utc']} desired={snapshot.get('desired')} running={snapshot.get('running')} healthy={healthy}" + (f" error={snapshot['error']}" if "error" in snapshot else ""), flush=True)
        if args.once:
            break
        time.sleep(15)


if __name__ == "__main__":
    main()
