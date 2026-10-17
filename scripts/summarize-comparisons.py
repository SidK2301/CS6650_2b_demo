"""Summarize exported measurement-only Locust statistics; no invented results."""
import csv
import json
from pathlib import Path
import statistics

root = Path(__file__).resolve().parents[1]
r = root / 'results' / 'locust'
rows = []
for client in ['http', 'fast']:
    for index in range(1, 4):
        run = f'{client}-{index}'
        with (r / f'{run}_stats.csv').open() as f:
            total = next(x for x in csv.DictReader(f) if x['Name'] == 'Aggregated')
        with (r / f'{run}_cpu.csv').open() as f:
            cpu = [float(x['process_cpu_percent']) for x in csv.DictReader(f) if x['phase'] == 'measurement']
        rows.append({'run': run, 'client': 'HttpUser' if client == 'http' else 'FastHttpUser',
                     'requests': int(total['Request Count']), 'failures': int(total['Failure Count']),
                     'rps': float(total['Requests/s']), 'p50_ms': float(total['50%']),
                     'p95_ms': float(total['95%']), 'mean_ms': float(total['Average Response Time']),
                     'generator_cpu_mean_percent': statistics.mean(cpu), 'generator_cpu_max_percent': max(cpu)})
with (r / 'comparison-runs.csv').open('w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=rows[0].keys()); writer.writeheader(); writer.writerows(rows)
summary = {}
for client in ['HttpUser', 'FastHttpUser']:
    values = [x for x in rows if x['client'] == client]
    summary[client] = {metric: {'median': statistics.median(x[metric] for x in values),
                               'min': min(x[metric] for x in values), 'max': max(x[metric] for x in values)}
                       for metric in ['rps', 'p50_ms', 'p95_ms', 'generator_cpu_mean_percent', 'generator_cpu_max_percent']}
(r / 'comparison-summary.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(summary, indent=2))
