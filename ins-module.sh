#!/bin/bash
set -e

cd "$(dirname "$0")"

if ! command -v python3 &>/dev/null; then
  echo "ERROR: python3 not found — install it first"
  exit 1
fi

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

.venv/bin/pip install -q -r requirements.txt
echo "OK: modules installed"
