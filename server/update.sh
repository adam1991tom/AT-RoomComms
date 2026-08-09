#!/usr/bin/env bash
set -Eeuo pipefail
if [[ $EUID -ne 0 ]]; then exec sudo bash "$0" "$@"; fi
cd "$(dirname "$0")"
mkdir -p backups
STAMP=$(date +%Y%m%d-%H%M%S)
docker run --rm -v roomcomms-data:/data -v "$PWD/backups":/backup alpine sh -c "tar czf /backup/roomcomms-data-$STAMP.tar.gz -C /data ." || true
docker compose build --pull
docker compose up -d --remove-orphans
docker image prune -f >/dev/null
echo "Updated. Backup: backups/roomcomms-data-$STAMP.tar.gz"
docker compose ps
