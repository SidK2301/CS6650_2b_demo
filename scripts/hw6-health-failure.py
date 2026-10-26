#!/usr/bin/env python3
"""Short, reversible target-group health-path experiment; run only during its separate load test."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import signal
import subprocess
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-group", required=True)
    parser.add_argument("--host", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seconds", type=int, default=90)
    args = parser.parse_args()
    if not 30 <= args.seconds <= 120:
        parser.error("observation must be 30–120 seconds")
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def aws(operation, *options):
        return json.loads(subprocess.check_output(
            ["aws", "elbv2", operation, "--region", "us-west-2", "--output", "json", *options],
            text=True, timeout=20))

    def record(data):
        data["utc"] = datetime.now(timezone.utc).isoformat()
        with args.output.open("a") as stream:
            stream.write(json.dumps(data) + "\n")

    def interrupted(signum, frame):
        raise KeyboardInterrupt("Restore health path before exit")

    signal.signal(signal.SIGTERM, interrupted)
    original = aws("describe-target-groups", "--target-group-arns", args.target_group)["TargetGroups"][0]["HealthCheckPath"]
    if original != "/health":
        raise RuntimeError("Expected /health before starting; refusing to overwrite an unexpected configuration")
    record({"event": "start", "original_path": original, "maximum_seconds": args.seconds})
    # The finally block covers a partially successful update and normal/interrupted observation.
    try:
        aws("modify-target-group", "--target-group-arn", args.target_group,
            "--health-check-path", "/hw6-intentionally-missing-health")
        deadline = time.monotonic() + args.seconds
        unhealthy_since = None
        while time.monotonic() < deadline:
            targets = aws("describe-target-health", "--target-group-arn", args.target_group)["TargetHealthDescriptions"]
            sample = {"event": "probe", "targets": targets}
            try:
                with urlopen(args.host.rstrip("/") + "/products/search?q=Electro", timeout=5) as response:
                    sample["search_status"] = response.status
            except HTTPError as error:
                sample["search_status"] = error.code
            except (URLError, TimeoutError) as error:
                sample["search_error"] = str(error)
            record(sample)
            states = [target["TargetHealth"]["State"] for target in targets]
            if states and all(state == "unhealthy" for state in states):
                unhealthy_since = unhealthy_since or time.monotonic()
                if time.monotonic() - unhealthy_since >= 10:
                    break
            time.sleep(5)
    finally:
        aws("modify-target-group", "--target-group-arn", args.target_group, "--health-check-path", original)
        restored = aws("describe-target-groups", "--target-group-arns", args.target_group)["TargetGroups"][0]["HealthCheckPath"]
        record({"event": "restored", "health_path": restored})
        if restored != original:
            raise RuntimeError("Health-path restoration verification failed")
        print("Restored and verified /health. Wait for target recovery before further tests.")


if __name__ == "__main__":
    main()
