#!/bin/sh
set -eu
RUN=${1:?run name required}
TARGET=${2:?host required}
PROFILE=${3:-search_spike.py}
case "$RUN" in *[!a-zA-Z0-9_-]*|'') echo 'Invalid run name' >&2; exit 2;; esac
case "$PROFILE" in search_spike.py|search_ramp.py) ;; *) echo 'Invalid profile' >&2; exit 2;; esac
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
mkdir -p "$ROOT/results/hw6"
shasum -a 256 "$ROOT/locust/search.py" "$ROOT/locust/$PROFILE" > "$ROOT/results/hw6/${RUN}_workload.sha256"
docker image inspect hw5-locust:2.46.6 --format '{{.Id}}' > "$ROOT/results/hw6/${RUN}_generator-image.txt"
docker run -d --name "hw6-$RUN" \
 -v "$ROOT/locust:/mnt/locust:ro" -v "$ROOT/results:/results" \
 -e RESULT_DIR=/results/hw6 -e "RUN_NAME=$RUN" -e LOAD_GENERATOR=laptop-docker \
 hw5-locust:2.46.6 -f "/mnt/locust/$PROFILE" SearchUser --headless --host "$TARGET" \
 --csv "/results/hw6/$RUN" --csv-full-history --html "/results/hw6/$RUN.html" \
 --logfile "/results/hw6/$RUN.log" --only-summary
