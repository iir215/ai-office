#!/bin/bash
# Stores one secret in backend/.env without it ever appearing on screen or in a chat.
# usage: bash scripts/set_secret.sh NAME     (then type/paste the value; the input is hidden)
set -e
cd "$(dirname "$0")/../backend"
[ -n "$1" ] || { echo "usage: set_secret.sh NAME"; exit 1; }
read -r -s -p "Value for $1 (input is hidden), then Enter: " V; echo
[ -n "$V" ] || { echo "empty value, nothing saved"; exit 1; }
cp .env ".env.bak.secret"
if grep -q "^$1=" .env; then
  python3 - "$1" "$V" <<'PY'
import sys, re
name, val = sys.argv[1], sys.argv[2]
lines = open(".env", encoding="utf-8").read().split("\n")
lines = [f"{name}={val}" if l.startswith(name + "=") else l for l in lines]
open(".env", "w", encoding="utf-8").write("\n".join(lines))
PY
else
  [ -n "$(tail -c1 .env)" ] && echo >> .env
  echo "$1=$V" >> .env
fi
echo "$1 saved (${#V} characters)"
