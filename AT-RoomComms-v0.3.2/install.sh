#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
echo "============================================================"
echo " AT RoomComms Server v0.3.2"
echo "============================================================"
if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required. Installing Docker..."
  curl -fsSL https://get.docker.com | sudo sh
fi
sudo systemctl enable --now docker 2>/dev/null || true

# Use one permanent data volume across all RoomComms versions.
if ! sudo docker volume inspect roomcomms-data >/dev/null 2>&1; then
  OLD=$(sudo docker volume ls --format '{{.Name}}' | grep -E 'roomcomms.*data|roomcomms-data' | head -n 1 || true)
  sudo docker volume create roomcomms-data >/dev/null
  if [ -n "$OLD" ] && [ "$OLD" != "roomcomms-data" ]; then
    echo "Migrating existing RoomComms data from $OLD..."
    sudo docker run --rm -v "$OLD":/old:ro -v roomcomms-data:/new alpine sh -c 'cp -a /old/. /new/'
  fi
fi

# Remove the previous container only; persistent data is untouched.
sudo docker rm -f at-roomcomms >/dev/null 2>&1 || true
sudo docker compose up -d --build
IP=$(hostname -I 2>/dev/null | awk '{print $1}')
echo
echo "AT RoomComms v0.3.2 is running."
echo "Open: http://${IP:-SERVER-IP}:5070"
echo "Admin login: adam / changeme"
echo "Speaker Preview login: speakerpreview / changeme"
echo "IMPORTANT: Change the default passwords after first login."
sudo docker compose ps
