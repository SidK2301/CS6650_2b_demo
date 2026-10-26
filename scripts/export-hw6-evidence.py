#!/usr/bin/env python3
"""Export matched CloudWatch and Prometheus windows for a completed HW6 run."""
import argparse
from datetime import datetime, timedelta
import json
from pathlib import Path
import subprocess
from urllib.parse import urlencode
from urllib.request import urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run")
    parser.add_argument("--scaling", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    window = json.loads((root / "results/hw6" / f"{args.run}_window.json").read_text())
    start = datetime.fromisoformat(window["start_utc"])
    end = datetime.fromisoformat(window["end_utc"])
    folder = root / "evidence/hw6" / args.run
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "window.json").write_text(json.dumps(window, indent=2) + "\n")
    for metric in ("CPUUtilization", "MemoryUtilization"):
        command = ["aws", "cloudwatch", "get-metric-statistics", "--region", "us-west-2",
                   "--namespace", "AWS/ECS", "--metric-name", metric, "--dimensions",
                   "Name=ClusterName,Value=cs6650-hw5-product-cluster",
                   "Name=ServiceName,Value=cs6650-hw5-product", "--start-time", start.isoformat(),
                   "--end-time", (end + timedelta(minutes=2)).isoformat(), "--period", "60",
                   "--statistics", "Average", "Maximum", "--output", "json"]
        data = json.loads(subprocess.check_output(command, text=True, timeout=30))
        data["Datapoints"].sort(key=lambda point: point["Timestamp"])
        (folder / f"{metric}.json").write_text(json.dumps(data, indent=2) + "\n")
        print(f"{metric}: {len(data['Datapoints'])} minute samples (includes up to 2m after test)")
    queries = {
        "rate": 'sum(rate(requests_total{route="/products/search",status="200"}[1m]))',
        "p50": 'histogram_quantile(0.5,sum by(le)(rate(request_duration_seconds_bucket{route="/products/search"}[1m])))',
        "p95": 'histogram_quantile(0.95,sum by(le)(rate(request_duration_seconds_bucket{route="/products/search"}[1m])))',
        "errors": 'sum(rate(errors_total{route="/products/search"}[1m]))',
        "up": 'up{job="product-api"}',
    }
    for name, query in queries.items():
        url = "http://localhost:9090/api/v1/query_range?" + urlencode({
            "query": query, "start": start.timestamp(), "end": end.timestamp(), "step": 5})
        with urlopen(url, timeout=30) as response:
            data = json.load(response)
        if data.get("status") != "success":
            raise RuntimeError(f"Prometheus query failed: {name}")
        (folder / f"prometheus-{name}.json").write_text(json.dumps(data, indent=2) + "\n")
    if args.scaling:
        def aws(service, operation, *options):
            return json.loads(subprocess.check_output(
                ["aws", service, operation, "--region", "us-west-2", "--output", "json", *options],
                text=True, timeout=30))
        lb = aws("elbv2", "describe-load-balancers", "--names", "cs6650-hw5-product-alb")["LoadBalancers"][0]
        group = aws("elbv2", "describe-target-groups", "--names", "cs6650-hw5-product-tg")["TargetGroups"][0]
        lb_suffix = lb["LoadBalancerArn"].split(":loadbalancer/")[1]
        group_suffix = "targetgroup/" + group["TargetGroupArn"].split(":targetgroup/")[1]
        dimensions = ["Name=ClusterName,Value=cs6650-hw5-product-cluster", "Name=ServiceName,Value=cs6650-hw5-product"]
        specs = [
            ("DesiredTaskCount", "ECS/ContainerInsights", "Average", dimensions),
            ("RunningTaskCount", "ECS/ContainerInsights", "Average", dimensions),
            ("RequestCount", "AWS/ApplicationELB", "Sum", ["Name=LoadBalancer,Value=" + lb_suffix]),
            ("TargetResponseTime", "AWS/ApplicationELB", "Average", ["Name=LoadBalancer,Value=" + lb_suffix]),
            ("HealthyHostCount", "AWS/ApplicationELB", "Minimum", ["Name=LoadBalancer,Value=" + lb_suffix, "Name=TargetGroup,Value=" + group_suffix]),
        ]
        for metric, namespace, statistic, dims in specs:
            data = aws("cloudwatch", "get-metric-statistics", "--namespace", namespace,
                       "--metric-name", metric, "--dimensions", *dims,
                       "--start-time", start.isoformat(), "--end-time", (end + timedelta(minutes=2)).isoformat(),
                       "--period", "60", "--statistics", statistic)
            data["Datapoints"].sort(key=lambda point: point["Timestamp"])
            (folder / f"{metric}.json").write_text(json.dumps(data, indent=2) + "\n")
        data = aws("cloudwatch", "get-metric-statistics", "--namespace", "AWS/ApplicationELB",
                   "--metric-name", "TargetResponseTime", "--dimensions", "Name=LoadBalancer,Value=" + lb_suffix,
                   "--start-time", start.isoformat(), "--end-time", (end + timedelta(minutes=2)).isoformat(),
                   "--period", "60", "--extended-statistics", "p95")
        data["Datapoints"].sort(key=lambda point: point["Timestamp"])
        (folder / "TargetResponseTime-p95.json").write_text(json.dumps(data, indent=2) + "\n")
        expression = "SEARCH('{ECS/ContainerInsights,ClusterName,ServiceName,TaskId} MetricName=\"TaskCpuUtilization\" ClusterName=\"cs6650-hw5-product-cluster\" ServiceName=\"cs6650-hw5-product\"', 'Average', 60)"
        data = aws("cloudwatch", "get-metric-data", "--metric-data-queries",
                   json.dumps([{"Id": "taskcpu", "Expression": expression}]),
                   "--start-time", start.isoformat(), "--end-time", (end + timedelta(minutes=2)).isoformat())
        (folder / "TaskCpuUtilization.json").write_text(json.dumps(data, indent=2) + "\n")
        for metric in ("rates", "p95"):
            query = ('sum by(instance)(rate(requests_total{route="/products/search",status="200"}[1m]))' if metric == "rates"
                     else 'histogram_quantile(0.95,sum by(le,instance)(rate(request_duration_seconds_bucket{route="/products/search"}[1m])))')
            url = "http://localhost:9090/api/v1/query_range?" + urlencode({"query": query, "start": start.timestamp(), "end": end.timestamp(), "step": 5})
            with urlopen(url, timeout=30) as response:
                data = json.load(response)
            (folder / f"prometheus-task-{metric}.json").write_text(json.dumps(data, indent=2) + "\n")
        data = aws("application-autoscaling", "describe-scaling-activities", "--service-namespace", "ecs",
                   "--resource-id", "service/cs6650-hw5-product-cluster/cs6650-hw5-product",
                   "--scalable-dimension", "ecs:service:DesiredCount")
        (folder / "scaling-activities.json").write_text(json.dumps(data, indent=2) + "\n")
        tasks = aws("ecs", "list-tasks", "--cluster", "cs6650-hw5-product-cluster",
                    "--service-name", "cs6650-hw5-product", "--desired-status", "STOPPED")["taskArns"]
        if tasks:
            data = aws("ecs", "describe-tasks", "--cluster", "cs6650-hw5-product-cluster", "--tasks", *tasks[:100])
            stopped = [{"taskArn": task["taskArn"], "stopCode": task.get("stopCode"),
                        "stoppedReason": task.get("stoppedReason"), "stoppedAt": task.get("stoppedAt"),
                        "containers": [{"name": c["name"], "exitCode": c.get("exitCode"), "reason": c.get("reason")} for c in task.get("containers", [])]}
                       for task in data["tasks"]]
            (folder / "stopped-tasks.json").write_text(json.dumps(stopped, indent=2) + "\n")
    print(f"Saved evidence under {folder}")


if __name__ == "__main__":
    main()
