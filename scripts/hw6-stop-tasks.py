#!/usr/bin/env python3
"""Stop a specified number of running lab tasks, recording exact failure-injection times."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    def aws(operation, *options):
        return json.loads(subprocess.check_output(
            ["aws", "ecs", operation, "--region", "us-west-2", "--output", "json", *options],
            text=True, timeout=30))

    arns = aws("list-tasks", "--cluster", "cs6650-hw5-product-cluster", "--service-name",
               "cs6650-hw5-product", "--desired-status", "RUNNING")["taskArns"]
    tasks = aws("describe-tasks", "--cluster", "cs6650-hw5-product-cluster", "--tasks", *arns)["tasks"] if arns else []
    running = [task for task in tasks if task["lastStatus"] == "RUNNING"]
    if not 1 <= args.count < len(running):
        raise RuntimeError("Choose at least one task and leave at least one running; all-unhealthy is a separate health-path test")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for task in running[:args.count]:
        event = {"utc": datetime.now(timezone.utc).isoformat(), "action": "stop-task", "taskArn": task["taskArn"]}
        with args.output.open("a") as stream:
            stream.write(json.dumps(event) + "\n")
        response = aws("stop-task", "--cluster", "cs6650-hw5-product-cluster", "--task", task["taskArn"],
                       "--reason", f"HW6 controlled {args.count}-task resilience experiment")
        event = {"utc": datetime.now(timezone.utc).isoformat(), "action": "stop-task-result", "task": response["task"]}
        with args.output.open("a") as stream:
            stream.write(json.dumps(event) + "\n")
        print("Stopped", task["taskArn"].rsplit("/", 1)[-1])


if __name__ == "__main__":
    main()
