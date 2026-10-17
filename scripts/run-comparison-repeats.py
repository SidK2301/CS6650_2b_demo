"""Run the four remaining matched experiments sequentially; never overlap load."""
import datetime
import json
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
results = root / "results" / "locust"
target = subprocess.check_output([str(root / 'scripts/task-ip.sh')], text=True).strip()
for run, client in [("http-2", "ProductHttpUser"), ("fast-2", "ProductFastHttpUser"), ("http-3", "ProductHttpUser"), ("fast-3", "ProductFastHttpUser")]:
    meta = {"client": client, "users": 50, "spawn_rate": 10, "warmup_seconds": 20,
            "measurement_seconds": 180, "wait_seconds": [.05, .15],
            "mix": {"GET": .9, "POST": .1}, "target": f"http://{target}:8080",
            "locust_version": "2.46.6", "workers": 1,
            "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()}
    (results / f"{run}_metadata.json").write_text(json.dumps(meta, indent=2) + '\n')
    cmd = ['docker', 'run', '--rm', '--name', f'hw5-locust-{run}',
           '-e', 'WARMUP_SECONDS=20', '-e', f'RUN_NAME={run}', '-e', 'RESULT_DIR=/results',
           '-v', f'{root}/locust:/mnt/locust:ro', '-v', f'{results}:/results',
           'hw5-locust:2.46.6', '-f', '/mnt/locust/locustfile.py', client,
           '--headless', '--host', meta['target'], '-u', '50', '-r', '10',
           '--run-time', '200s', '--csv', f'/results/{run}', '--csv-full-history',
           '--html', f'/results/{run}.html', '--only-summary']
    print(f'Starting {run}: {client}', flush=True)
    with (results / f'{run}.log').open('w') as log:
        outcome = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT)
    meta['finished_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    meta['exit_code'] = outcome.returncode
    (results / f"{run}_metadata.json").write_text(json.dumps(meta, indent=2) + '\n')
    if outcome.returncode:
        raise SystemExit(f'{run} failed: inspect its log before continuing')
    print(f'Completed {run}', flush=True)
print('All four remaining comparison runs completed.', flush=True)
