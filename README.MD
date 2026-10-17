# HW5 — Go Product API

Go/Gin Product API with in-memory storage, Terraform deployment to AWS ECS,
Locust load tests, and local Prometheus/Grafana monitoring. Based on
[RuidiH/CS6650_2b_demo](https://github.com/RuidiH/CS6650_2b_demo).

| Location | Contents |
|---|---|
| `src/product-service.go` | Product API server |
| `src/product_service_test.go` | Handler, contract, and concurrency tests |
| `src/Dockerfile` | Server image |
| `terraform/` | ECR, ECS, logging, and networking |
| `docker-compose.yml`, `monitoring/` | Local Prometheus and Grafana |
| `scripts/` | API verification, task IP, and Locust runs |
| `results/`, `evidence/` | Load-test data, logs, and screenshots |

## Part II: Product API

### Contract and assumptions

[api.yaml](api.yaml) defines two Product endpoints. IDs 1–1000 are seeded at
startup; POST updates existing products and returns 404 for missing products,
as confirmed by the instructor. Invalid GET IDs return 404 because GET lists
no 400; seeding and this invalid-ID behavior are implementation assumptions.
Authentication is omitted pending clarification of the specification's global
API-key/bearer declaration.

Routes work at both root and `/v1`. Required JSON keys are case-sensitive;
extra properties are accepted. Path and body IDs must agree. All numeric
fields are int32; IDs must be positive, and weight may be zero. SKU length is
1–100 characters and manufacturer length is 1–200, counted as Unicode
characters. Bodies over 1 MiB return 400; trailing-slash routes return 404.
Errors contain `error`, `message`, and optional field-specific `details`.

| Endpoint | Status | Trigger |
|---|---|---|
| GET /products/{id} | 200 | Existing ID |
| GET /products/{id} | 404 | Unknown or invalid ID |
| GET /products/{id} | 500 | Enabled controlled fault |
| POST /products/{id}/details | 204 | Valid update; empty response |
| POST /products/{id}/details | 400 | Invalid input or path/body ID mismatch |
| POST /products/{id}/details | 404 | Valid input for an unknown ID |
| POST /products/{id}/details | 500 | Enabled controlled fault |

### Run locally

Requires Go 1.27.1 for the Docker build; the Go module specifies Go 1.24 or newer.
From the repository root:

```sh
cd src
go test -race ./...
FAULT_INJECTION=true go run .
```

Alternatively, stop any process using port 8080 and run Docker:

```sh
docker build -t hw5-product:local ./src
docker run --rm --name hw5-product -p 127.0.0.1:8080:8080 \
  -e FAULT_INJECTION=true hw5-product:local
```

Fault injection is a local response-code demonstration: it is enabled only
when `FAULT_INJECTION` is exactly `true`. Compose defaults to false and ECS
sets false explicitly; the fault header then produces normal 200/204 responses.

### Copy-paste requests

In another terminal, use the local server above, or set BASE to the ECS URL.
The last two examples require the local fault-enabled server.

```sh
BASE=http://localhost:8080  # or http://$TASK_IP:8080
BODY='{"product_id":1,"sku":"ABC-123","manufacturer":"Acme","category_id":1,"weight":0,"some_other_id":1}'

curl -i "$BASE/products/1"                         # 200
curl -i "$BASE/products/1001"                      # 404
curl -i -X POST "$BASE/products/1/details" \
  -H 'Content-Type: application/json' -d "$BODY"    # 204, empty body
curl -i -X POST "$BASE/products/1/details" \
  -H 'Content-Type: application/json' \
  -d '{"product_id":1,"sku":""}'                    # 400
curl -i -X POST "$BASE/products/1001/details" \
  -H 'Content-Type: application/json' \
  -d '{"product_id":1001,"sku":"ABC-123","manufacturer":"Acme","category_id":1,"weight":0,"some_other_id":1}' # 404

# Local only: FAULT_INJECTION=true
curl -i -H 'X-Fault-Inject: 500' "$BASE/products/1"  # 500
curl -i -X POST -H 'X-Fault-Inject: 500' \
  -H 'Content-Type: application/json' -d "$BODY" \
  "$BASE/products/1/details"                       # 500
```

`EXPECT_FAULTS=true ./scripts/verify-api.sh "$BASE"` checks all seven cases;
use `EXPECT_FAULTS=false` for normal servers. Race tests cover concurrent
GET/POST, required fields, zero weight, Unicode boundaries, and recovered 500
metrics/logs. API checks passed with native Go, Docker, and Compose.

![Native Go responses](evidence/api/phase1-go-responses.png)
![Docker responses](evidence/api/phase1-docker-responses.png)

## Part III: Deploy to ECS

Requires Terraform, Docker Engine/Desktop, AWS CLI, Python 3 for experiment
helper scripts, and valid AWS lab credentials including the session token.
Clone this repository, start Docker, and verify AWS access. From the repo root:

```sh
aws sts get-caller-identity
export DOCKER_HOST=$(docker context inspect --format '{{.Endpoints.docker.Host}}')
cd terraform
terraform init
# Replace with your load generator's public IPv4 address.
terraform plan -var='allowed_cidrs=["YOUR_PUBLIC_IP/32"]' -out=hw5.tfplan
terraform apply hw5.tfplan
cd ..
```

Wait for the ECS task to become RUNNING and HEALTHY, then discover its address:

```sh
TASK_IP=$(./scripts/task-ip.sh)
curl -i "http://$TASK_IP:8080/health"
EXPECT_FAULTS=false ./scripts/verify-api.sh "http://$TASK_IP:8080"
```

The service `cs6650-hw5-product` runs in `us-west-2` with one Linux X86_64
Fargate task, 0.25 vCPU, and 512 MiB. Terraform builds linux/amd64, tags the
image with a hash of source/build inputs, and waits for the push before ECS
creation. The `/health` container check uses interval 30s, timeout 5s, three
retries, and start period 10s. CloudWatch logs are in `/ecs/cs6650-hw5-product`.
The public IP changes on redeployment; rerun task-ip.sh. Allow additional load
generator IPs through `allowed_cidrs` if needed. Keep credentials, state, and
private variables outside Git; `.gitignore` covers them.

![ECS task and sizing](evidence/ecs/phase2-ecs-running.png)
![Healthy container](evidence/ecs/phase2-ecs-healthy.png)
![Remote API verification](evidence/ecs/phase2-ecs-api-responses.png)

Cleanup from the repository root:

```sh
cd terraform
terraform destroy -var='allowed_cidrs=["YOUR_PUBLIC_IP/32"]'
```

All eight deployment resources were removed after testing; the state is empty
and the cluster is INACTIVE with zero tasks. Saved public IPs are no longer live.

## Part IV: Locust load tests

### Test design and reproduction

Locust 2.46.6 (Python 3.13.15) ran in native local Docker containers. Prepare
its image, then start a comparison run from the repository root:

```sh
docker pull locustio/locust:2.46.6
docker tag locustio/locust:2.46.6 hw5-locust:2.46.6
TASK_IP=$(./scripts/task-ip.sh)
./scripts/start-locust.sh ProductHttpUser http-1 "http://$TASK_IP:8080" 50
# After the run stops, release port 8089 before the next run.
docker stop hw5-locust-http-1
./scripts/start-locust.sh ProductFastHttpUser fast-1 "http://$TASK_IP:8080" 50
```

Each comparison uses 50 users, spawn rate 10/s, one process, 90% GET and 10%
valid POST on seeded IDs, and 50–150 ms think time. Statistics reset after
20 seconds of warm-up, followed by 180 seconds of measurement. Three runs per
client alternate; `scripts/run-comparison-repeats.py` runs the remaining four
sequentially after stopping the fast-1 container. Use unique container/run names.
The dashboard's Current RPS is rolling; the table uses full measurement-period
Requests/s from CSV. Raw results and CPU samples are in `results/locust/`.

### HttpUser versus FastHttpUser

| Client | RPS median (range) | p50 ms median (range) | p95 ms median (range) | Generator CPU mean: median across runs |
|---|---|---|---|---|
| HttpUser | 241.8 (241.7–242.8) | 95 (95–96) | 150 (150–150) | 30.8% |
| FastHttpUser | 244.8 (244.5–245.1) | 93 (93–93) | 150 (150–150) | 16.8% |


All six runs had zero failures. Generator CPU is process CPU: 100% means one
core, not the whole laptop. FastHttpUser increased median throughput about
1.2% and lowered generator CPU, while p95 stayed unchanged. Think time and
network latency dominate the request cycle at this load. FastHttpUser uses
geventhttpclient instead of requests and reduces client overhead; it does not
inherently accelerate server requests ([Locust documentation](https://docs.locust.io/en/latest/increase-performance.html)).
Per-run values are in `results/locust/comparison-runs.csv`; CloudWatch exports
have one-minute resolution in `results/cloudwatch/`.

![HttpUser run](evidence/locust/phase2-httpuser-run1.png)
![FastHttpUser run](evidence/locust/phase2-fasthttpuser-run1.png)
![Comparison CPU and memory](evidence/ecs/phase2-ecs-comparison-metrics.png)

### Stress test

`./scripts/start-stress.sh "http://$TASK_IP:8080"` runs FastHttpUser with zero
wait time, one-minute levels of 50, 100, 200, 400, 700, and 1000 users, and spawn
rate 50/s. The first 20 seconds are warm-up. The table averages rolling RPS and
takes median rolling percentiles over each stage from +20s to two seconds
before its end, excluding ramps; these are not full-stage distributions.

| Users | Mean rolling RPS | Median rolling p50 ms | Median rolling p95 ms | Generator CPU mean / max |
|---|---|---|---|---|
| 50 | 441 | 96 | 140 | 16.5% / 21.0% |
| 100 | 948 | 99 | 140 | 25.5% / 28.9% |
| 200 | 1807 | 99 | 140 | 25.5% / 28.0% |
| 400 | 2838 | 115 | 200 | 37.7% / 44.6% |
| 700 | 3316 | 190 | 330 | 45.8% / 58.3% |
| 1000 | 3394 | 270 | 490 | 47.3% / 59.7% |


The knee appears around 400–700 users. From 700 to 1000 users, throughput
increased about 2% while rolling p95 rose from 330 to 490 ms. The run completed
756,499 requests with zero failures; aggregate p95 across all levels was
380 ms. ECS CPU approached 100%, memory peaked near 13.1%, and generator CPU
stayed below 60% of one core, supporting server CPU saturation. One-minute
stages and a single 0.25-vCPU task limit generalization; profiling would be
needed to isolate costs within the server.

![Stress statistics](evidence/locust/phase2-stress-statistics.png)
![Stress throughput and latency](evidence/locust/phase2-stress-charts.png)
![User levels](evidence/locust/phase2-stress-users.png)
![Stress CPU and memory](evidence/ecs/phase2-ecs-stress-metrics.png)

## Part V: Local RED dashboard and logs

From the repository root, with port 8080 free:

```sh
docker compose up -d --build
python3 scripts/prepare-local-observability.py
```

This records 90 seconds idle, then a local FastHttpUser run: 50 users, spawn
rate 10/s, 20s warm-up, 180s measurement, 50–150 ms think time. Traffic is 88%
valid GET, 10% valid POST, 1% expected 404, and 1% expected 400. Port 8089 must
be free. App: localhost:8080; Prometheus: localhost:9090;
[Grafana dashboard](http://localhost:3000/d/hw5-red): admin / hw5-local-only
(local demo credentials; all published ports bind to 127.0.0.1).
Dashboard provisioning and JSON are in `monitoring/grafana/`.

`requests_total`, `errors_total`, and `request_duration_seconds` track rate,
non-2xx responses, and latency by route/method/status. Unknown routes use
`unmatched`; `/metrics` and `/health` are excluded. One-minute rate windows
smooth traffic transitions. Histogram buckets span 0.1 ms–10s; most local
requests fall in the first bucket, so p50/p95 are interpolated estimates.
Idle latency has no samples. Server duration differs from Locust's end-to-end
latency. JSON request logs include endpoint, method, status, and duration_ms.

The recorded idle baseline began at 02:58:38 UTC on October 17, 2026
(10:58:38 PM EDT October 16); load began at 03:00:08 UTC (11:00:08 PM EDT).
Locust measured 88,553 requests with zero unexpected failures. Including
warm-up, logs contain 97,160 business requests: 85,468 with 200, 9,777 with 204,
966 with 400, and 949 with 404—1.97% non-2xx. Locust resets after warm-up;
these log totals include it. Settings/timestamps are in
`results/locust/local-red_metadata.json`.

Locust failures mean responses violated expectations; RED errors include all
non-2xx, including expected 400/404. Dashboard errors are per endpoint: about
1/89 of GETs and 1/11 of POSTs, explaining roughly 1% versus 9%, while the
combined share is about 2%.

![Idle versus loaded RED panels](evidence/grafana/phase2-grafana-idle-loaded.png)
![Matching request logs](evidence/logs/phase2-local-request-logs.png)

The log excerpt is [phase2-local-run-excerpt.jsonl](evidence/logs/phase2-local-run-excerpt.jsonl);
its 03:00 UTC timestamps match 11:00 PM EDT on the dashboard. For live logs,
use `docker compose logs --no-log-prefix app`; stop the stack with
`docker compose down`.

I would use the dashboard to spot changes in rate, errors, and tail latency
over time. I would use logs to inspect individual requests during that interval.
