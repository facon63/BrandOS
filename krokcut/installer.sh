#!/usr/bin/env bash
# Installation sur Mac / Linux
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null; then
  echo "Installe Python 3.10+ (https://www.python.org/downloads/ ou 'brew install python')."
  exit 1
fi
if ! command -v ffmpeg >/dev/null; then
  echo "Installe ffmpeg : 'brew install ffmpeg' (Mac) ou 'sudo apt install ffmpeg' (Linux)."
  exit 1
fi

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
echo
echo "Installation terminée ! Lance ./lancer.sh pour ouvrir KrokCut."
