# HW6 - Product Search, Monitoring, and Elastic Scaling

Siddhi Kore | CS6650

Go/Gin product API with 100,000 generated products, bounded search, AWS Fargate deployment, ALB health checks, CPU target tracking, and per-task Prometheus/Grafana monitoring. Extends the HW5 implementation based on [RuidiH/CS6650_2b_demo](https://github.com/RuidiH/CS6650_2b_demo).

## Report and evidence

- [Two-page report PDF](output/pdf/HW6_Report.pdf) - figures embedded for Canvas submission.
- [Editable report](output/HW6_Report.md).
- [All 13 captioned screenshots](evidence/hw6/SCREENSHOTS.md).
- [Part II findings](evidence/hw6/part2-findings.md) and [Part III findings](evidence/hw6/part3-findings.md).
- [Local exactly-100 log/test evidence](evidence/hw6/checked100-test.log).
- [AWS cleanup verification](evidence/hw6/cleanup-verification.json).
- `results/hw6/`: Locust CSV histories, HTML reports, UTC windows and workload hashes.

## Implementation

`src/product-service.go` initializes 100,000 products in `sync.Map`. Search checks exactly 100 products using case-insensitive name/category containment, returns at most 20 matches, and logs `checked=100`. Iteration order is unspecified. Generated names are internal because the supplied Product schema has no name field. GET and POST use the same concurrent store; POST updates existing IDs only.

Search is available at `/products/search?q=Electro` and `/v1/products/search?q=Electro`. The required `q` accepts 1-100 Unicode characters; missing/empty/oversized/invalid UTF-8 input returns 400. Response fields are `products`, `total_found`, and duration-string `search_time`. See [product-search.yaml](product-search.yaml). Existing GET `/products/{id}` and POST `/products/{id}/details` follow [api.yaml](api.yaml). `/health` and `/metrics` support monitoring.

## Local verification

```sh
cd src
go test -race ./...
go run .
```

For local dashboards, run `docker compose up -d --build` from the repository root. Grafana uses localhost:3000 and Prometheus localhost:9090. Local Grafana credentials are configured in `docker-compose.yml`.

## AWS infrastructure

`terraform-ecr/` owns ECR independently. `terraform/` owns ECS, ALB, security groups, logging, autoscaling and the Part III dashboard. Each task uses 256 CPU units and 512 MB. ALB targets use IP/8080, `/health` every 30 seconds, healthy threshold 2 and ECS grace period 60 seconds. Target tracking uses 70% CPU, minimum 2 / maximum 4 tasks and 300-second cooldowns. Configuration variables are in `terraform/variables.tf`; local credentials, state and tfvars are excluded from Git.

Prometheus uses `monitoring/prometheus-ecs.yml` plus `scripts/discover-ecs-targets.py` to discover individual task endpoints. Apply `docker-compose.ecs-monitoring.yml` alongside the base Compose file when observing AWS. Metrics are not scraped through the ALB.

## Experiments

`locust/search.py` defines the shared FastHttpUser query set and zero wait. `scripts/run-hw6-load.sh RUN HOST USERS DURATION` saves results under `results/hw6/`; spike/ramp profiles use `scripts/run-hw6-spike.sh`. `scripts/export-hw6-evidence.py RUN --scaling` exports matched metrics. The required 20-user test did not saturate CPU; 200 users became the breaking-point workload and was reused in Part III.

One task at 200 users achieved 1,278 RPS and 300 ms client p95. Two tasks behind ALB achieved 1,492 RPS and 210 ms p95. The longer CPU-triggered run scaled from two to three tasks with zero failed requests. Failure experiments and timing limitations are documented in the report and evidence.

## Cleanup

The application stack was destroyed and local containers stopped after evidence export. ECR and the tested image were retained; monitoring data, state and experiment files were preserved. To tear down a recreated application deployment, use `terraform destroy` only from `terraform/`, preserving the independent ECR root. No live deployment is needed to inspect the submitted evidence.
