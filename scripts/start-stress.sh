#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TARGET=${1:?Target URL required}
docker run -d --name hw5-locust-stress-1 -p 127.0.0.1:8089:8089 \
 -e WARMUP_SECONDS=20 -e RUN_NAME=stress-1 -e RESULT_DIR=/results \
 -e WORKLOAD=performance -e STRESS=true -e STRESS_SHAPE=true \
 -v "$ROOT/locust:/mnt/locust:ro" -v "$ROOT/results/locust:/results" \
 hw5-locust:2.46.6 -f /mnt/locust/locustfile.py ProductFastHttpUser \
 --autostart --host "$TARGET" --csv /results/stress-1 --csv-full-history \
 --html /results/stress-1.html --logfile /results/stress-1.log --web-host 0.0.0.0
