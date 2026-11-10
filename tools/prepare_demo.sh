#!/bin/sh
# Prepare the live demo: a fresh system with 3 simulated hours of history for all 30 patients.
# Run from the project folder, with Docker running and .env filled in:
#
#   sh tools/prepare_demo.sh
#
# Then, during the demo, start P001's scripted deterioration (about 50 seconds at 30x):
#
#   sh tools/prepare_demo.sh story
#
set -eu

STORY_START="2026-01-05T03:00:00Z"   # straight after the 3 hours of history

if [ "${1:-}" = "story" ]; then
    docker compose run --rm simulator sh -c "python -m simulator.cli patients --out /tmp/demo >/dev/null && \
        python -m simulator.cli scenario --patients-csv /tmp/demo/sim_patients.csv --patient P001 \
        --transport mqtt --mqtt-host mqtt --speedup 30 --start $STORY_START"
    exit 0
fi

echo "1/3 Fresh start (deletes the demo database and broker data)"
docker compose down --volumes
docker compose up --build --detach

echo "2/3 Waiting for the API"
until curl -fs http://localhost:8000/health >/dev/null; do sleep 2; done

echo "3/3 Three simulated hours of readings for 30 patients"
docker compose run --rm simulator python -m simulator.cli live --transport mqtt --mqtt-host mqtt \
    --days 0.125 --speedup 0

echo "Ready: http://localhost:8080 (C01 / admin, passwords from .env)."
echo "During the demo: sh tools/prepare_demo.sh story"
