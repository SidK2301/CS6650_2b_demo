# HW5 — Go Product API

Forked from RuidiH/CS6650_2b_demo. HW1–4 remain in the CS6650 repository.

## Contract decisions

The supplied api.yaml is the contract. Products 1–1000 are seeded at startup;
POST updates existing products only. Unknown IDs return 404. Invalid GET IDs
(non-integer, nonpositive, or int32 overflow) return 404 because GET lists no 400.
These interpretations are assumptions pending instructor clarification.

The global authentication declaration has no credential configuration in the
assignment. Authentication is omitted as a course-scope assumption pending
clarification; this is not full compliance with that global declaration.

Both /products/... and /v1/products/... are supported. Extra JSON properties
are accepted. Path and body product IDs must agree. Required integer presence
is validated separately from value, so weight 0 is valid. Strings are measured
in Unicode characters. Required JSON property names are case-sensitive. Bodies
are limited to 1 MiB; oversized input returns 400. Trailing-slash routes return
404 rather than redirecting. Invalid fields include an explanatory details value.
Updates disappear on restart; separate tasks do not share data.

| Endpoint | Status | Trigger |
|---|---|---|
| GET /products/{id} | 200 | Existing ID |
| GET /products/{id} | 404 | Unknown or invalid ID |
| GET /products/{id} | 500 | Enabled controlled fault |
| POST /products/{id}/details | 204 | Valid update; empty response |
| POST /products/{id}/details | 400 | Invalid path/body, missing or invalid fields, ID mismatch |
| POST /products/{id}/details | 404 | Valid input for unknown ID |
| POST /products/{id}/details | 500 | Enabled controlled fault |

Errors always contain error and message; details is optional.

## Starter inspection

- Module: text/main; starter Go directive: 1.24.0.
- Starter Dockerfile: Go 1.24 Alpine builder, Linux amd64 binary, Alpine runtime.
- Terraform container_port: 8080; region: us-west-2.
- Fargate defaults: one task, 256 CPU units (0.25 vCPU), 512 MiB memory.
- No ALB and no health check are configured in the starter.
- awslogs sends stdout to /ecs/<service_name>, retention seven days.
- Phase 2 must explicitly disable fault injection in the task definition and
  configure a health check. Image-push ordering and deployment updates are pending review.

## Local Go

```sh
cd src
go test -race ./...
FAULT_INJECTION=true go run .
```

In another terminal, from the repository root:

```sh
./scripts/verify-api.sh http://localhost:8080
```

The script demonstrates all seven endpoint/status combinations and verifies
that a subsequent GET sees the POST update. Fault injection only works when
FAULT_INJECTION is exactly true; otherwise the header is ignored.

## Docker

```sh
docker build -t hw5-product:local ./src
docker run --rm --name hw5-product -p 127.0.0.1:8080:8080 -e FAULT_INJECTION=true hw5-product:local
./scripts/verify-api.sh http://localhost:8080
```

Stop the Go process before binding Docker to the same port. Fault injection
is only for local verification and must be disabled for normal performance tests.

## Local monitoring

```sh
docker compose up -d --build
```

App: http://localhost:8080; Prometheus: http://localhost:9090;
Grafana: http://localhost:3000 (local-only demo login admin / hw5-local-only;
all three published ports bind to 127.0.0.1).
Open the provisioned HW5 RED dashboard. The dashboard JSON is committed under
monitoring/grafana/dashboards. This stack is local only.

```sh
# Enable controlled 500s only for the response-code demonstration.
FAULT_INJECTION=true docker compose up -d app
./scripts/verify-api.sh http://localhost:8080
# Restore normal operation before measured runs.
FAULT_INJECTION=false docker compose up -d app
docker compose logs --no-log-prefix app
```

Compose disables fault injection by default. The explicit true override above
is only for the response-code demonstration.
Prometheus scrapes the Compose service name app:8080, not localhost.
Stop with `docker compose down`.

## Instrumentation

requests_total and errors_total use route/method/status labels. Duration is
request_duration_seconds with buckets from 0.1 ms through 10 seconds. Unknown
routes use unmatched. /metrics and /health are excluded from metrics but still
produce one JSON request log each. slog writes request time, endpoint, method,
status, and duration_ms to stdout. Metrics/logging wraps recovery, so recovered
panics are recorded as 500. A recovered panic also emits a separate ERROR
diagnostic with its value; http.ErrAbortHandler propagates to the HTTP server.
Dashboards describe server duration; Locust measures
end-to-end latency. They need not match.

## Evidence and remaining phases

Phase 1 evidence includes native/Docker response verification and a local RED
dashboard. ECS experiments, measured local Locust evidence, deployment
instructions, and interview notes are pending.

## Phase 1 verification

Go handler tests passed with `go test -race ./...`, including concurrent
GET/POST, required fields, Unicode boundaries, zero weight, recovered 500
metrics/logs, and metric exclusions. All seven response cases passed under
native Go, standalone Docker, and Compose. All four provisioned dashboard
queries returned data. No AWS resources have been created.

Screenshots captured by the student:

![Native Go response verification](evidence/api/phase1-go-responses.png)

![Docker response verification](evidence/api/phase1-docker-responses.png)

![Local monitoring setup verification](evidence/grafana/phase1-grafana-check.png)

The Grafana screenshot is a setup check with deliberate errors, not Part IV
performance evidence or the final Part V idle-versus-loaded experiment.
A short Phase 1 JSON log excerpt is in evidence/logs/phase1-local-requests.jsonl;
the final Part V excerpt must come from the later measured local Locust run.

Phase 2 has not started.

## Deployment architecture preflight

Terraform builds linux/amd64 and the task runtime explicitly selects Linux X86_64.
The matching local image is built with:

```sh
docker build --platform linux/amd64 -t hw5-product:amd64 ./src
```

On Apple Silicon this image runs under emulation. Its timing is not performance
evidence. The local monitoring stack uses the host's native architecture.

Pre-deployment checks passed: expanded race tests and all seven HTTP response
cases. The amd64 image reported healthy with the command below; the temporary
container was removed afterward. No host port is needed because the check runs
inside the container.

```sh
docker run -d --name hw5-health --platform linux/amd64 \
  --health-cmd 'wget -qO- http://localhost:8080/health || exit 1' \
  --health-interval 5s hw5-product:amd64
# Allow the first health check to finish, then inspect:
docker inspect --format '{{.State.Health.Status}}' hw5-health
docker rm -f hw5-health
```

Terraform validation passed using AWS provider 6.7.0 and Docker provider 2.25.0.
The Docker provider's build platform setting is documented in its
[versioned resource documentation](https://github.com/kreuzwerker/terraform-provider-docker/blob/v2.25.0/docs/resources/image.md).
ECS health-check configuration, deployment fault settings, image tagging, and
push ordering remain Phase 2 deployment work.
