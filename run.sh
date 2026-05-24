#!/bin/bash
set -e

cd "$(dirname "$0")"

if ! command -v python3 &>/dev/null; then
  echo "ERROR: python3 not found — install it first"
  exit 1
fi

if [ -f .env ]; then
  set -a && source .env && set +a
fi

if [ -z "$SERVER_URL" ] || [ -z "$SERVER_ADMIN_USER" ] || [ -z "$SERVER_PASSWORD" ]; then
  echo "ERROR: missing env vars — SERVER_URL, SERVER_ADMIN_USER, SERVER_PASSWORD required"
  exit 1
fi

if ! command -v nginx &>/dev/null; then
  echo "ERROR: nginx not found"
  exit 1
fi

CONF_DIR="/home/${SERVER_ADMIN_USER}/conf/web"
if [ ! -d "$CONF_DIR" ]; then
  echo "ERROR: conf dir not found: $CONF_DIR"
  exit 1
fi

if [ ! -w "$CONF_DIR" ]; then
  echo "ERROR: no write permission on $CONF_DIR — run as root or correct user"
  exit 1
fi

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

.venv/bin/pip install -q -r requirements.txt

.venv/bin/python main.py "${1:-request.json}"
