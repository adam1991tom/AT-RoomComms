#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
echo "============================================================"
echo " AT RoomComms Server v0.3.1"
echo "============================================================"
if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required. Installing Docker..."
  curl -fsSL https://get.docker.com | sudo sh
fi
sudo systemctl enable --now docker 2>/dev/null || true
sudo docker compose up -d --build
IP=$(hostname -I 2>/dev/null | awk '{print $1}')
echo
echo "AT RoomComms is running."
echo "Open: http://${IP:-SERVER-IP}:5070"
sudo docker compose ps
