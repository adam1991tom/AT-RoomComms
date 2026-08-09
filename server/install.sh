#!/usr/bin/env bash
set -Eeuo pipefail
if [[ $EUID -ne 0 ]]; then exec sudo bash "$0" "$@"; fi
command -v docker >/dev/null 2>&1 || { echo "Docker is required."; exit 1; }
docker compose version >/dev/null 2>&1 || { echo "Docker Compose v2 is required."; exit 1; }
cd "$(dirname "$0")"
[[ -f .env ]] || cp .env.example .env
docker compose up -d --build
PORT=$(awk -F= '/^ROOMCOMMS_PORT=/{print $2}' .env | tail -1); PORT=${PORT:-5070}
echo
echo "AT RoomComms Server is installed."
echo "Open: http://$(hostname -I | awk '{print $1}'):${PORT}"
docker compose ps
