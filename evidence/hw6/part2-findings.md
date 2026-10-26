# Part II measured findings (draft; measurements complete)

| Run | Requests | Failures | RPS | Client median | Client p95 | Highest published minute-average CPU |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 5,909 | 0 | 49.4 | 93 ms | 150 ms | 8.3% |
| breaking20 | 33,327 | 0 | 175.4 | 97 ms | 160 ms | 22.5% |

Configuration: one Fargate task, 256 CPU units, 512 MB memory; 100,000 products at startup; exactly 100 checked per search; maximum 20 returned. Laptop-hosted FastHttpUser, zero wait, identical query list and generator image. Required configured run times were 120s and 180s; UTC event windows are preserved, including the roughly 10s observed overrun on the 20-user run.

The 20-user test did not establish a CPU or memory bottleneck. Throughput rose from 49.4 to 175.4 RPS (run-wide averages) with zero failures. Client p95 rose from 150 to 160 ms, about 6.7%, while server duration remained sub-millisecond on Grafana. A more demanding exploration is needed before claiming scaling is necessary.

Single-user AWS searches reported about 0.15–0.21 ms search_time, while sequential laptop requests had about 200 ms median end-to-end time. This demonstrates a large client/network contribution; search_time covers only part of application handling and cannot account for the entire request path. The assignment's <20ms end-to-end expectation was not met from this laptop.

CPU and RED agreed that increasing user count increased work, without failures or significant server latency degradation. CPU/memory cannot show client network latency. Grafana server duration also excludes client/network time, so compare both dashboards with Locust.

At 20 users there is no evidence that doubling CPU is necessary or would materially reduce client latency. If the spike test reaches CPU saturation and server duration rises, extra CPU would become a plausible remedy; that is a prediction until tested.

ECR ownership is separate from the application root, and pushed images are retained by keep_remotely=true. No application work was inflated to force expected CPU percentages.

## Creative spike exploration

A separate five-minute shape used 20 users for 60 seconds, 100 for 180 seconds, then 20 for 60 seconds. The workload, query set, and zero wait remained unchanged. It completed 181,945 requests with zero failures; run-wide client p95 was 170 ms. Published full-load minute-average CPU was approximately 80–82%. The 100-user stage sustained roughly 860–900 RPS. This demonstrates substantially increased CPU pressure, but it does not establish failure or sustained saturation; an additional separately recorded higher-load test is needed to establish a breaking point. Full profile, UTC window, CSV history, and generator CPU samples are retained.

## Saturation experiment: 200 users for 3 minutes

The separate saturation200 run kept the original search workload and generator image unchanged. It completed 229,842 requests with zero failures, about 1,278 RPS, a 120 ms client median, and 300 ms client p95. The full-load CloudWatch minutes averaged 99.93% and 99.40% CPU. Memory averaged about 15%, with a sampled maximum near 16%, so CPU reached its limit well before memory.

Client p95 doubled relative to the 5-user baseline (150 to 300 ms). Doubling users from the 100-user spike stage yielded a much smaller proportional throughput increase (approximately 860–900 to 1,278 RPS), alongside CPU saturation. These observations support a CPU capacity limit, even though no requests failed. The spike's whole-run RPS must not be compared as if it were a steady 100-user run, because it also includes 20-user stages.

Grafana's measured server p95 remained around 0.25 ms despite the larger client p95. Do not claim the handler-duration graph showed a latency spike: it did not. Its timer begins in application middleware, so time before middleware starts is outside that duration. Increased pre-handler queueing/scheduling or network/client delay is a possible explanation, not separately proven by these measurements. CPU, request metrics, and Locust together reveal more than either dashboard alone.

Increasing CPU from 256 to 512 units is a reasonable prediction for reducing CPU pressure and increasing capacity at this load, assuming CPU scales effectively. It was not tested, and it would not eliminate network RTT. Horizontal scaling should next be tested with the exact same 200-user, 3-minute workload through the ALB; retain the original 20-user result as the required assignment test.

## Screenshot evidence

See the [captioned screenshot gallery](SCREENSHOTS.md) for the supplied dashboard captures.

- [Figure 2: Five-user baseline](baseline/phase2-baseline-dashboards.png)
- [Figure 3: Twenty-user required test](breaking20/phase2-20users-dashboards.png)
- [Figure 4: Spike to 100 users](spike100/phase2-spike100-dashboards.png)
- [Figure 5: Single-task saturation at 200 users](saturation200/phase2-saturation200-dashboards.png)

## Review clarification

With zero wait, users / whole-run RPS implies approximately 101 ms at five users and 114 ms at twenty. This closed-loop client/network delay limits offered load, so the 22.5% CPU reading alone does not prove under-checking. Local request-log evidence in checked100-test.log and TestSearchContractAndBound verify exactly 100 checks even after the 20-result cap is reached. These are local checks, not retained logs from every AWS load-test request. The 200-user run is explicitly the breaking-point test reused by the Part III core comparison.

The separate ten-request sequential AWS verification did not preserve its client implementation or connection-reuse settings. Its 200 ms median is not comparable to the FastHttpUser five-user p95, and is excluded from same-method performance comparisons. No new AWS measurement was performed after teardown.
