#!/usr/bin/env bash
# Pull latest code and rebuild the app containers.
# Usage: cd /opt/nokia && sudo bash deploy/update-vps.sh
set -euo pipefail
cd "$(dirname "$0")/.."

git pull --ff-only
docker compose build
docker compose up -d --remove-orphans
docker image prune -f
docker compose ps
