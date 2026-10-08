#!/bin/bash
# Lancé par l'app KrokCut : démarre le serveur en arrière-plan (s'il ne tourne pas déjà)
# puis ouvre l'interface dans le navigateur. On l'arrête avec le bouton « Quitter » de l'interface.
cd "$(dirname "$0")" || exit 1
URL="http://127.0.0.1:8765"
mkdir -p workspace
if [ -x bin/ffmpeg ]; then
  export KROKCUT_FFMPEG_DIR="$PWD/bin"
fi
# Un KrokCut tourne déjà ? S'il date d'avant une mise à jour, on le relance (sinon l'ancienne
# version continuerait de tourner avec la nouvelle interface et rien ne marcherait).
if /usr/bin/curl -fs "$URL/api/config" >/dev/null 2>&1 \
   && ! /usr/bin/curl -fs "$URL/api/version" 2>/dev/null | grep '"current":true' >/dev/null; then
  /usr/bin/curl -fs -X POST "$URL/api/quit" >/dev/null 2>&1 || true
  for _ in $(seq 1 40); do
    /usr/bin/curl -fs "$URL/api/config" >/dev/null 2>&1 || break
    sleep 0.25
  done
fi
if ! /usr/bin/curl -fs "$URL/api/config" >/dev/null 2>&1; then
  nohup ./.venv/bin/python -m krokcut serve --no-browser > workspace/serveur.log 2>&1 < /dev/null &
  for _ in $(seq 1 80); do
    /usr/bin/curl -fs "$URL/api/config" >/dev/null 2>&1 && break
    sleep 0.25
  done
fi
if [ -z "${KROKCUT_NO_OPEN:-}" ]; then
  /usr/bin/open "$URL"
fi
