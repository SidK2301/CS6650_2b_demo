#!/bin/sh
set -eu
# Usage: sh scripts/run-hw6-load.sh baseline http://TASK_IP:8080 5 2m
RUN=${1:?run name required}
TARGET=${2:?host required}
USERS=${3:?users required}
DURATION=${4:?duration required}
case "$RUN" in *[!a-zA-Z0-9_-]*|'') echo 'Invalid run name' >&2; exit 2;; esac
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
mkdir -p "$ROOT/results/hw6"
shasum -a 256 "$ROOT/locust/search.py" > "$ROOT/results/hw6/${RUN}_workload.sha256"
docker image inspect hw5-locust:2.46.6 --format '{{.Id}}' > "$ROOT/results/hw6/${RUN}_generator-image.txt"
docker run -d --name "hw6-$RUN" -p 127.0.0.1:8089:8089 \
 -v "$ROOT/locust:/mnt/locust:ro" -v "$ROOT/results:/results" \
 -e RESULT_DIR=/results/hw6 -e "RUN_NAME=$RUN" -e LOAD_GENERATOR=laptop-docker \
 hw5-locust:2.46.6 -f /mnt/locust/search.py SearchUser --autostart \
 --host "$TARGET" -u "$USERS" -r 20 -t "$DURATION" \
 --csv "/results/hw6/$RUN" --csv-full-history --html "/results/hw6/$RUN.html" \
 --logfile "/results/hw6/$RUN.log" --web-host 0.0.0.0
