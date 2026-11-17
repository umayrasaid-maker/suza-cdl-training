#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
if [ -z "${ADMIN_KEY:-}" ]; then
  echo "Set ADMIN_KEY to a strong private password to enable the admin dashboard."
fi
python3 -m pip install -r requirements.txt
python3 app.py
