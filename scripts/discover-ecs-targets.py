#!/usr/bin/env python3
"""Refresh Prometheus targets from running ECS tasks; no AWS resources are modified."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def discover(args):
    def aws(service, operation, *options):
        return json.loads(subprocess.check_output(
            ["aws", service, operation, "--region", args.region, "--output", "json", *options],
            text=True, timeout=30,
        ))

    arns = aws("ecs", "list-tasks", "--cluster", args.cluster,
               "--service-name", args.service, "--desired-status", "RUNNING")["taskArns"]
    if not arns:
        return []
    result = aws("ecs", "describe-tasks", "--cluster", args.cluster, "--tasks", *arns)
    if result.get("failures"):
        raise RuntimeError("ECS task discovery returned failures; preserving previous targets")
    targets = []
    for task in result["tasks"]:
        if task["lastStatus"] != "RUNNING":
            continue
        eni = None
        for attachment in task.get("attachments", []):
            for detail in attachment.get("details", []):
                if detail["name"] == "networkInterfaceId":
                    eni = detail["value"]
        if not eni:
            continue  # A task can still be attaching its interface.
        interfaces = aws("ec2", "describe-network-interfaces", "--network-interface-ids", eni)
        interface = interfaces["NetworkInterfaces"][0]
        ip = (interface.get("Association", {}).get("PublicIp") if args.address == "public"
              else interface.get("PrivateIpAddress"))
        if not ip:
            raise RuntimeError(f"No {args.address} IP on {eni}; check monitoring network placement")
        targets.append({"targets": [f"{ip}:{args.port}"], "labels": {
            "instance": task["taskArn"].rsplit("/", 1)[-1],
            "ecs_service": args.service,
        }})
    return targets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("region", "cluster", "service"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--address", choices=("public", "private"), default="public")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--interval", type=int, default=15)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "monitoring/targets/ecs.json")
    args = parser.parse_args()
    if args.interval < 1 or not 1 <= args.port <= 65535:
        parser.error("interval must be positive and port must be 1–65535")
    while True:
        try:
            targets = discover(args)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            temporary = args.output.with_suffix(".tmp")
            temporary.write_text(json.dumps(targets, indent=2) + "\n")
            os.replace(temporary, args.output)
            print(f"Updated {len(targets)} task targets", flush=True)
        except (subprocess.SubprocessError, OSError, ValueError, KeyError, RuntimeError) as error:
            print(f"Discovery failed: {error}", file=sys.stderr, flush=True)
            if args.once:
                raise SystemExit(1)
        if args.once:
            return
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
