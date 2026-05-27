#!/bin/bash
set -e

cd "$(dirname "$0")"

# ---- parse flags ----
JSON_FILE=""
ENV_FILE=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --file|--nginx) JSON_FILE="$2"; shift 2 ;;
    --env)  ENV_FILE="$2";  shift 2 ;;
    *) echo "ERROR: unknown flag $1"; exit 1 ;;
  esac
done

if [ -z "$JSON_FILE" ]; then
  echo "ERROR: --nginx <path> required"
  exit 1
fi

# ---- checks ----
if ! command -v python3 &>/dev/null; then
  echo "ERROR: python3 not found — install it first"
  exit 1
fi

if [ -z "$ENV_FILE" ]; then
  DB_NAME=$(python3 -c "import json; d=json.load(open('$JSON_FILE')); print(d.get('db_name',''))" 2>/dev/null)
  if [ -z "$DB_NAME" ]; then
    echo "ERROR: db_name not found in $JSON_FILE"
    exit 1
  fi
  ENV_FILE="/home/www/manager/fin-source/env/.env.${DB_NAME}"
fi

if [ -f "$ENV_FILE" ]; then
  set -a && source "$ENV_FILE" && set +a
fi

if [ -z "$HESTIA_URL" ] || [ -z "$HESTIA_ADMIN_USER" ] || [ -z "$HESTIA_PASSWORD" ]; then
  echo "ERROR: missing env vars — HESTIA_URL, HESTIA_ADMIN_USER, HESTIA_PASSWORD required"
  exit 1
fi

if ! command -v nginx &>/dev/null; then
  echo "ERROR: nginx not found"
  exit 1
fi

CONF_DIR="/home/${HESTIA_ADMIN_USER}/conf/web"
if [ ! -d "$CONF_DIR" ]; then
  echo "ERROR: conf dir not found: $CONF_DIR"
  exit 1
fi

if [ ! -w "$CONF_DIR" ]; then
  echo "ERROR: no write permission on $CONF_DIR — run as root or correct user"
  exit 1
fi

# ---- run ----
.venv/bin/python nginx-setport.py "$JSON_FILE"
