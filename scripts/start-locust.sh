#!/bin/sh
set -eu
# Usage: start-locust.sh ProductHttpUser http-1 http://TASK_IP:8080 [users]
CLASS=${1:?User class required}
RUN=${2:?Run name required}
TARGET=${3:?Target URL required}
USERS=${4:-50}
case "$CLASS" in ProductHttpUser|ProductFastHttpUser) ;; *) echo 'Invalid class' >&2; exit 2;; esac
case "$RUN" in *[!a-zA-Z0-9_-]*|'') echo 'Invalid run name' >&2; exit 2;; esac
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
mkdir -p "$ROOT/results/locust"
docker run -d --name "hw5-locust-$RUN" --network "${LOCUST_NETWORK:-bridge}" -p 127.0.0.1:8089:8089 \
 -e WARMUP_SECONDS=20 -e "RUN_NAME=$RUN" -e RESULT_DIR=/results \
 -e "WORKLOAD=${WORKLOAD:-performance}" -e "STRESS=${STRESS:-false}" \
 -v "$ROOT/locust:/mnt/locust:ro" -v "$ROOT/results/locust:/results" \
 hw5-locust:2.46.6 -f /mnt/locust/locustfile.py "$CLASS" \
 --autostart --host "$TARGET" -u "$USERS" -r 10 --run-time 200s \
 --csv "/results/$RUN" --csv-full-history --html "/results/$RUN.html" \
 --logfile "/results/$RUN.log" --web-host 0.0.0.0
