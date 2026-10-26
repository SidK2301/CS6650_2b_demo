# Part III measured findings (draft; longer scaling and failure experiments pending)

## Core comparison

Application image, source workload hash, generator image, query list, zero wait, spawn rate, 200 users and configured 3-minute duration matched the single-task saturation run. Only host changed to the ALB. Two tasks and two healthy targets were confirmed before load.

| Deployment | Requests | Failures | Whole-run RPS | Client median | Client p95 |
|---|---:|---:|---:|---:|---:|
| One task, direct | 229,842 | 0 | 1,278 | 120 ms | 300 ms |
| ALB, two tasks | 268,482 | 0 | 1,492 | 110 ms | 210 ms |

Client p95 improved 30%; throughput improved about 16.8%. These are observed improvements, not a claim of linear scaling. A sampled traffic window showed roughly 762–765 RPS on each task, evidence of balanced load.

The first available full-load CPU minute averaged about 84.9% across tasks, versus approximately 99.4–99.9% for the saturated single task. Desired/running counts remained 2 in the initially exported core-test window. Preserve the final metric refresh and timeline before concluding whether any late scaling occurred.

The actual target-tracking high alarm uses three 60-second evaluation periods above 70%. Its low alarm uses 15 60-second periods below 63%. Therefore, configured 300-second cooldowns alone do not guarantee scale-in after five minutes. Alarm evaluation, metric publication, scheduling, task startup and target registration all contribute to observed timing.

## Scaling-trigger interpretation to finalize after the longer event

Handler-duration p95 stayed low in Part II even at CPU saturation. A duration-only trigger on that signal would risk reacting late or not at all for this workload. CPU is a reasonable trigger because fixed per-request work consumes CPU and observed utilization tracks rising demand. Use Locust/ALB latency to assess user experience; middleware duration excludes time before handler execution. Requests-in-flight was not instrumented, so do not claim its actual trigger time. Finalize this answer with the actual scale-out timeline rather than predictions.

## Observed scale-out: 10-minute, 200-user run

The run started at 06:15:09.938 UTC and ended at 06:25:09.781 UTC. It completed 957,475 requests with zero failures, including during scaling. Whole-run RPS was 1,596 and client p95 was 210 ms.

AWS scaling activity records a CPU-alarm-triggered desired-count increase to 3 at 06:21:40.698 UTC (about 6m31s after test start). The 15-second observer first saw desired=3/running=2/pending=1 at 06:21:53.224 and three running/healthy tasks at 06:22:26.471. Treat observer timestamps as sampled bounds, not exact transition instants. AWS marked the scaling activity successful at 06:22:45.108.

Full-load service CPU was about 84–87% with two tasks, dropping to about 63–64% in the final full minutes with three. A post-scale snapshot showed approximately 578 RPS on each task. Recent client p95 dropped from roughly 220 ms to 180 ms after scale-out, with no request failures.

CPU was the better trigger than this middleware-duration signal for this workload: CPU clearly exceeded 70% while Grafana handler-duration p95 remained low. A duration-only trigger on that signal could have missed the pressure. ALB target latency and Locust latency provide a wider view of delay than the handler timer. No requests-in-flight metric was collected, so its hypothetical trigger time cannot be stated as a measured result.

Scaling delay includes metric publication and alarm evaluation as well as startup and target health. The observed delay demonstrates why the 3-minute core test was insufficient to show scale-out, even though it already showed benefits from two tasks.

## Resilience: single and multiple task stops

A separate 200-user, six-minute run completed 582,363 requests at about 1,618 RPS with zero failures and 190 ms whole-run client p95. One task was stopped at 06:31:23.908 UTC. The observer later recorded two healthy targets and then three again at 06:32:45.549, about 82 seconds after injection. Two tasks were stopped at 06:33:27.507/28.307; healthy targets fell to one and recovered to three at 06:34:42.401, about 74 seconds after the first stop in that pair. These are sampled recovery bounds, not exact health-transition times.

The desired count stayed three. ECS replaced stopped tasks to maintain desired capacity; that replacement is service self-healing, distinct from CPU-based autoscaling changing the desired count. ALB routed to remaining healthy targets while replacements initialized. No failures were observed in this particular run; this does not guarantee zero errors for every failure scenario. The task-stop event log, target timeline, Locust history, and stopped reasons support the finding.

## Health-check failure and fail-open

A separate four-minute, 200-user test completed 397,996 requests at about 1,659 RPS, zero failures, and 180 ms whole-run client p95. The target-group path was temporarily changed from /health to a nonexistent path starting at 06:41:36.318 UTC; /health was restored and verified at 06:42:57.804.

Three consecutive probes at 06:42:44.223, 06:42:50.277 and 06:42:56.230 recorded all three registered targets unhealthy while the search endpoint still returned HTTP 200 through the ALB. This is direct evidence consistent with ALB fail-open, not evidence that health checks were working normally. ECS began replacing tasks; three healthy targets were subsequently restored. Keep health-events.jsonl and stopped-tasks.json as primary evidence, because short state changes can be missed by one-minute dashboard samples. A successful controlled test does not guarantee uninterrupted service for every all-unhealthy scenario.

## Screenshot evidence

See the [captioned screenshot gallery](SCREENSHOTS.md) for the supplied dashboard captures.

- [Figure 6: ALB core comparison: CPU and tasks](alb-core200/phase3-core200-dashboards.png)
- [Figure 7: ALB core comparison: requests and latency](alb-core200/phase3-core200-alb-metrics.png)
- [Figure 8: Scale-out: CPU and capacity](alb-scale200/phase3-scaleout-dashboards.png)
- [Figure 9: Scale-out: ALB latency](alb-scale200/phase3-scaleout-alb-metrics.png)
- [Figure 10: Task-stop resilience: CPU and capacity](alb-resilience200/phase3-resilience-dashboards.png)
- [Figure 11: Task-stop resilience: ALB metrics](alb-resilience200/phase3-resilience-alb-metrics.png)
- [Figure 12: Health-check failure and recovery](alb-health200/phase3-health-failure-dashboards.png)
- [Figure 13: Health-check failure: ALB metrics](alb-health200/phase3-health-failure-alb-metrics.png)

## Request metric versus CPU timing

At 06:15 UTC, ALB TargetResponseTime p95 was 103.65 ms while service minute-average CPU was 41.22%. At 06:16, CPU average first exceeded 70% (86.93%) and ALB p95 was 108.37 ms. The load began at 06:15:09.938, so the 06:15 CPU bucket includes pre-load seconds and ramp-up. These aggregates do not establish that a latency trigger would fire earlier than CPU. CPU maximum was already 92.95% in the 06:15 bucket, so sub-minute ordering is not established. No latency-based scaling policy was tested. Source: alb-scale200/CPUUtilization.json and TargetResponseTime-p95.json.
