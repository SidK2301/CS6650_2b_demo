#!/usr/bin/env python3
"""Temporarily change one autoscaling field, save the configuration, then restore it."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import signal
import subprocess
import time

RESOURCE = "service/cs6650-hw5-product-cluster/cs6650-hw5-product"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--field", required=True, choices=("target_value", "scale_out_cooldown", "scale_in_cooldown", "min_capacity", "max_capacity"))
    parser.add_argument("--value", required=True, type=int)
    parser.add_argument("--seconds", type=int, default=120)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if not 15 <= args.seconds <= 900 or args.value < 1:
        parser.error("seconds must be 15–900 and value positive")

    def aws(operation, *options):
        return json.loads(subprocess.check_output(
            ["aws", "application-autoscaling", operation, "--region", "us-west-2", "--output", "json", *options],
            text=True, timeout=30))

    common = ["--service-namespace", "ecs", "--resource-id", RESOURCE, "--scalable-dimension", "ecs:service:DesiredCount"]
    policy = aws("describe-scaling-policies", *common)["ScalingPolicies"][0]
    target = aws("describe-scalable-targets", "--service-namespace", "ecs", "--resource-ids", RESOURCE)["ScalableTargets"][0]
    original = policy["TargetTrackingScalingPolicyConfiguration"]
    modified = dict(original)
    config_key = {"target_value": "TargetValue", "scale_out_cooldown": "ScaleOutCooldown", "scale_in_cooldown": "ScaleInCooldown"}
    if args.field in config_key:
        modified[config_key[args.field]] = args.value
        if args.field == "target_value" and args.value > 100:
            parser.error("CPU target must be at most 100")
    else:
        minimum = args.value if args.field == "min_capacity" else target["MinCapacity"]
        maximum = args.value if args.field == "max_capacity" else target["MaxCapacity"]
        if not 1 <= minimum <= maximum <= 4:
            parser.error("keep capacity within 1–4 and min <= max")

    def update(restore=False):
        if args.field in config_key:
            return aws("put-scaling-policy", *common, "--policy-name", policy["PolicyName"],
                       "--policy-type", "TargetTrackingScaling", "--target-tracking-scaling-policy-configuration",
                       json.dumps(original if restore else modified))
        return aws("register-scalable-target", *common, "--min-capacity", str(target["MinCapacity"] if restore else minimum),
                   "--max-capacity", str(target["MaxCapacity"] if restore else maximum))

    report = {"field": args.field, "trial_value": args.value, "duration_seconds": args.seconds,
              "original_policy": original, "original_min": target["MinCapacity"], "original_max": target["MaxCapacity"],
              "start_utc": datetime.now(timezone.utc).isoformat()}
    if args.field in config_key:
        report["trial_policy"] = modified
    else:
        report["trial_min"] = minimum
        report["trial_max"] = maximum
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def save():
        args.output.write_text(json.dumps(report, indent=2) + "\n")

    def interrupted(signum, frame):
        raise KeyboardInterrupt("Restore original scaling setting before exit")

    signal.signal(signal.SIGTERM, interrupted)
    save()
    try:
        report["update_response"] = update()
        report["applied_utc"] = datetime.now(timezone.utc).isoformat()
        save()
        time.sleep(args.seconds)
    finally:
        report["restore_response"] = update(restore=True)
        report["restored_utc"] = datetime.now(timezone.utc).isoformat()
        report["final_policy"] = aws("describe-scaling-policies", *common)["ScalingPolicies"][0]["TargetTrackingScalingPolicyConfiguration"]
        report["final_target"] = aws("describe-scalable-targets", "--service-namespace", "ecs", "--resource-ids", RESOURCE)["ScalableTargets"][0]
        save()
        if report["final_policy"] != original or report["final_target"]["MinCapacity"] != target["MinCapacity"] or report["final_target"]["MaxCapacity"] != target["MaxCapacity"]:
            raise RuntimeError("Original configuration was not fully restored; inspect saved report")
        print("Original policy and capacity bounds restored and verified.")


if __name__ == "__main__":
    main()
