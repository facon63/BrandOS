#!/usr/bin/env bash
# Rendu complet et reproductible :
#   out/intro_10s.mp4  (1920x1080, 30 fps, H.264 + AAC 48 kHz stéréo)
#   out/intro_3s.mp4   (version courte : accroche + logo + stinger)
#   out/logo_krok_et_mil.png (logo seul, fond transparent)
#   out/stinger.wav    (jingle final ~1 s + queue de réverbe)
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p out build/audio

echo "▶ 1/5 musique + SFX (Python)"
python3 audio/compose.py --out build/audio

echo "▶ 2/5 vidéo 10 s (Remotion)"
npx remotion render src/index.ts Intro build/intro_10s_video.mp4 --codec=h264 --crf=16 --pixel-format=yuv420p --muted --log=error

echo "▶ 3/5 vidéo 3 s (Remotion)"
npx remotion render src/index.ts Intro3s build/intro_3s_video.mp4 --codec=h264 --crf=16 --pixel-format=yuv420p --muted --log=error

echo "▶ 4/5 assemblage image + son (ffmpeg)"
for v in 10s 3s; do
  wav=build/audio/intro_mix.wav; [ "$v" = 3s ] && wav=build/audio/intro_3s_mix.wav
  ffmpeg -y -loglevel error -i "build/intro_${v}_video.mp4" -i "$wav" -map 0:v:0 -map 1:a:0 \
    -c:v copy -c:a aac -b:a 256k -ar 48000 -ac 2 -movflags +faststart "out/intro_${v}.mp4"
done
cp build/audio/stinger.wav out/stinger.wav

echo "▶ 5/5 logo PNG transparent"
npx remotion still src/index.ts LogoPNG build/logo_raw.png --image-format=png --log=error
python3 tools/finalize.py
