#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "============================================================"
echo " AT RoomComms Server v1.0.0"
echo "============================================================"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required. Installing Docker..."
  curl -fsSL https://get.docker.com | sh
fi

systemctl enable --now docker 2>/dev/null || true

if ! docker compose version >/dev/null 2>&1; then
  echo "ERROR: Docker Compose plugin is required."
  exit 1
fi

# Keep one permanent data volume for every RoomComms version.
if ! docker volume inspect roomcomms-data >/dev/null 2>&1; then
  echo "Creating permanent RoomComms data volume..."
  docker volume create roomcomms-data >/dev/null
fi

# Back up the existing SQLite database before V1 starts.
if docker run --rm -v roomcomms-data:/data alpine sh -c 'test -f /data/roomcomms.db' >/dev/null 2>&1; then
  echo "Backing up existing RoomComms database..."
  docker run --rm -v roomcomms-data:/data alpine sh -c 'cp /data/roomcomms.db /data/roomcomms-before-v1-$(date +%Y%m%d-%H%M%S).db'
fi

# Remove only the application container. Persistent data remains untouched.
docker rm -f at-roomcomms >/dev/null 2>&1 || true

echo "Building AT RoomComms v1.0.0..."
docker compose build --no-cache

echo "Starting AT RoomComms v1.0.0..."
docker compose up -d

sleep 5

echo
echo "Running version:"
if curl -fsS http://localhost:5070/api/health; then
  echo
else
  echo "Health endpoint is still starting. Check with: docker logs at-roomcomms"
fi

echo
IP=$(hostname -I 2>/dev/null | awk '{print $1}')
echo "============================================================"
echo " AT RoomComms v1.0.0 installation complete"
echo " Open: http://${IP:-SERVER-IP}:5070"
echo "============================================================"
docker compose ps
