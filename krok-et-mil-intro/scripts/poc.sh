#!/usr/bin/env bash
# Preuve de concept : 4 images clés (une par univers), planche de modèle, extrait audio de 3 s autour du DROP.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p poc
for id in PocU1:u1_cartoon PocU2:u2_post_apo PocU3:u3_medieval PocU4:u4_conclusion ModelSheet:model_sheet; do
  comp="${id%%:*}"; name="${id##*:}"
  npx remotion still src/index.ts "$comp" "poc/$name.png" --log=error
done
python3 audio/compose.py --excerpt 6.5625 3 --excerpt-out poc/audio_drop_3s.wav
python3 tools/check_heights.py | tee poc/hauteurs.txt
