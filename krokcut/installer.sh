#!/usr/bin/env bash
# Installation sur Mac / Linux
set -euo pipefail
cd "$(dirname "$0")"

# Whisper et ses dépendances ont des paquets prêts pour Python 3.10 à 3.13 : on en cherche un.
PY=""
for candidate in python3.12 python3.11 python3.13 python3.10 python3; do
  if command -v "$candidate" >/dev/null; then
    if "$candidate" -c 'import sys; sys.exit(0 if (3, 10) <= sys.version_info[:2] <= (3, 13) else 1)'; then
      PY="$candidate"
      break
    fi
  fi
done
if [ -z "$PY" ]; then
  echo "Il faut Python 3.10 à 3.13. Sur Mac : brew install python@3.12"
  exit 1
fi
if ! command -v ffmpeg >/dev/null; then
  echo "Installe ffmpeg : 'brew install ffmpeg' (Mac) ou 'sudo apt install ffmpeg' (Linux)."
  exit 1
fi

echo "Python utilisé : $($PY --version)"
"$PY" -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
chmod +x lancer.sh KrokCut.command 2>/dev/null || true
echo
echo "Installation terminée ! Lance ./lancer.sh (ou double-clique sur KrokCut.command) pour ouvrir KrokCut."
