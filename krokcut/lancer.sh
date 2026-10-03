#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -f .venv/bin/activate ]; then
  echo "Lance d'abord ./installer.sh"
  exit 1
fi
source .venv/bin/activate
python -m krokcut serve
