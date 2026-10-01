#!/usr/bin/env bash
# Assemble l'image et le son : out/video_<mode>.mp4 + out/mix.wav → out/altherion-vsl_<mode>.mp4
# Usage : tools/mux.sh photo|avatar
set -euo pipefail
cd "$(dirname "$0")/.."
MODE="${1:-avatar}"
ffmpeg -y -v error -i "out/video_${MODE}.mp4" -i out/mix.wav \
  -map 0:v -map 1:a -c:v libx264 -preset slow -crf 19 -profile:v high -pix_fmt yuv420p \
  -c:a aac -b:a 256k -ar 48000 -shortest -movflags +faststart \
  -metadata title="Altherion — De zéro à studio" -metadata language=fre \
  "out/altherion-vsl_${MODE}.mp4"
ffprobe -v error -show_entries format=duration,size,bit_rate -of default=nw=1 "out/altherion-vsl_${MODE}.mp4"
# Livrables versionnés : uniquement la variante anonyme (règles d'anonymat de la charte)
if [ "$MODE" = "avatar" ]; then
  mkdir -p livrables
  cp "out/altherion-vsl_avatar.mp4" out/altherion-vsl_musique-sfx.wav out/altherion-vsl.fr.srt livrables/
  echo "→ livrables/ mis à jour"
fi
