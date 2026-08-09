#!/usr/bin/env bash
set -Eeuo pipefail
if [[ $EUID -ne 0 ]]; then exec sudo bash "$0" "$@"; fi
cd "$(dirname "$0")"
if [[ "${1:-}" == "--delete-data" ]]; then
  docker compose down -v
  echo "Server and database deleted."
else
  docker compose down
  echo "Server removed. Database volume was preserved."
fi
