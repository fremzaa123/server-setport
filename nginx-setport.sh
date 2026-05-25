#!/bin/bash
set -e

cd "$(dirname "$0")"

# ---- parse flags ----
JSON_FILE="request.json"
ENV_FILE="/home/fin/.env.staging_db"

while [[ $# -gt 0 ]]; do
  case $1 in
    --file|--nginx) JSON_FILE="$2"; shift 2 ;;
    --env)  ENV_FILE="$2";  shift 2 ;;
    *) echo "ERROR: unknown flag $1"; exit 1 ;;
  esac
done

# ---- checks ----
if ! command -v python3 &>/dev/null; then
  echo "ERROR: python3 not found — install it first"
  exit 1
fi

if [ -f "$ENV_FILE" ]; then
  set -a && source "$ENV_FILE" && set +a
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

# ---- run ----
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

.venv/bin/pip install -q -r requirements.txt
.venv/bin/python main.py "$JSON_FILE"
