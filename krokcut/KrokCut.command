#!/usr/bin/env bash
# Double-clic sur Mac : installe au premier lancement, puis ouvre KrokCut dans le navigateur.
cd "$(dirname "$0")"
if [ ! -f .venv/bin/activate ]; then
  bash installer.sh || { echo; read -r -p "Installation impossible. Entrée pour fermer…"; exit 1; }
fi
bash lancer.sh
