#!/usr/bin/env bash
# KrokCut — installation (et mise à jour) sur Mac en une seule commande :
#
#   curl -fsSL https://raw.githubusercontent.com/facon63/BrandOS/claude/upbeat-fermi-qf074j/krokcut/install-mac.sh | bash
#
# Rien à installer avant : Python, ffmpeg et les dépendances sont téléchargés dans ~/KrokCut.
# À la fin, une app « KrokCut » apparaît dans Applications (et sur le Bureau) : double-clic pour lancer.
# Relancer la même commande met KrokCut à jour sans toucher aux épisodes ni aux réglages.
set -euo pipefail

REPO="facon63/BrandOS"
REF="${KROKCUT_REF:-claude/upbeat-fermi-qf074j}"
DEST="${KROKCUT_DIR:-$HOME/KrokCut}"
APPS="${KROKCUT_APP_DIR:-$HOME/Applications}"
PYTHON_VERSION="3.12"

step() { printf '\n\033[1;32m▶ %s\033[0m\n' "$1"; }
fail() { printf '\n\033[1;31m✖ %s\033[0m\n\n' "$1" >&2; exit 1; }

OS="$(uname -s)"
ARCH="$(uname -m)"
if [ "$OS" != "Darwin" ] && [ -z "${KROKCUT_ALLOW_NON_MAC:-}" ]; then
  fail "Ce script est fait pour Mac. Sous Windows, utilise installer.bat."
fi
command -v curl >/dev/null || fail "curl est introuvable."

mkdir -p "$DEST/bin"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# ---------------------------------------------------------------- 1. le code
step "1/4 Téléchargement de KrokCut"
if [ -n "${KROKCUT_SOURCE:-}" ]; then
  SRC="$KROKCUT_SOURCE"  # installation depuis un dossier local (tests)
else
  curl -fsSL "https://github.com/$REPO/archive/refs/heads/$REF.tar.gz" -o "$TMP/code.tar.gz" \
    || fail "Impossible de télécharger KrokCut (connexion internet ?)."
  tar -xzf "$TMP/code.tar.gz" -C "$TMP"
  SRC="$(find "$TMP" -mindepth 2 -maxdepth 2 -type d -name krokcut | head -1)"
  [ -n "$SRC" ] || fail "Archive inattendue : dossier krokcut introuvable."
fi
# KrokCut ouvert pendant la mise à jour : on le ferme, sinon l'ancienne version continuerait de tourner
if curl -fs http://127.0.0.1:8765/api/config >/dev/null 2>&1; then
  echo "KrokCut est ouvert : il est fermé pour la mise à jour (un traitement en cours reprendra avec « Continuer »)."
  curl -fs -X POST http://127.0.0.1:8765/api/quit >/dev/null 2>&1 || true
  for _ in $(seq 1 40); do
    curl -fs http://127.0.0.1:8765/api/config >/dev/null 2>&1 || break
    sleep 0.25
  done
fi
# Met à jour le code de KrokCut, et seulement lui : on ne supprime que les fichiers et dossiers que
# KrokCut a lui-même installés (liste fixe ci-dessous + ceux de la nouvelle version). Tout ce que
# tu as rangé dans ce dossier (bibliothèque de sons, rush…), les épisodes, les réglages, Python et
# ffmpeg restent intacts.
SHIPPED=".gitattributes .gitignore KrokCut.command README.md exemples install-mac.sh installer.bat installer.sh \
krokcut lancer-mac.sh lancer.bat lancer.sh requirements-dev.txt requirements.txt tests"
for name in $SHIPPED .pytest_cache .ruff_cache $(cd "$SRC" && ls -A); do
  case "$name" in workspace | .venv | bin | python) continue ;; esac
  rm -rf "${DEST:?}/$name"
done
(cd "$SRC" && tar -cf - --exclude workspace --exclude .venv --exclude bin --exclude python \
  --exclude __pycache__ --exclude .pytest_cache --exclude .ruff_cache .) | (cd "$DEST" && tar -xf -)
[ -f "$DEST/requirements.txt" ] || fail "Copie du code incomplète."

# ------------------------------------------------------------ 2. Python + dépendances
step "2/4 Python et dépendances (quelques minutes la première fois)"
case "$OS-$ARCH" in
  Darwin-arm64) UV_TRIPLE="aarch64-apple-darwin" ;;
  Darwin-x86_64) UV_TRIPLE="x86_64-apple-darwin" ;;
  Linux-x86_64) UV_TRIPLE="x86_64-unknown-linux-gnu" ;;
  Linux-aarch64) UV_TRIPLE="aarch64-unknown-linux-gnu" ;;
  *) fail "Processeur non pris en charge : $ARCH" ;;
esac
UV="$DEST/bin/uv"
if [ ! -x "$UV" ]; then
  curl -fsSL "https://github.com/astral-sh/uv/releases/latest/download/uv-$UV_TRIPLE.tar.gz" -o "$TMP/uv.tar.gz" \
    || fail "Impossible de télécharger l'installeur Python (uv)."
  tar -xzf "$TMP/uv.tar.gz" -C "$TMP"
  cp "$TMP/uv-$UV_TRIPLE/uv" "$UV"
  chmod +x "$UV"
fi
export UV_PYTHON_INSTALL_DIR="$DEST/python"
export UV_NO_PROGRESS=1
if [ ! -x "$DEST/.venv/bin/python" ]; then
  "$UV" venv --quiet --python "$PYTHON_VERSION" --python-preference only-managed "$DEST/.venv" \
    || fail "Impossible d'installer Python."
fi
"$UV" pip install --quiet --python "$DEST/.venv/bin/python" -r "$DEST/requirements.txt" \
  || fail "L'installation des dépendances a échoué."

# ------------------------------------------------------------------ 3. ffmpeg
step "3/4 ffmpeg"
ffmpeg_ok() {
  # (pas de grep -q : avec pipefail il couperait la sortie de ffmpeg et ferait échouer le test)
  "$1/ffmpeg" -hide_banner -encoders 2>/dev/null | grep libx264 >/dev/null && "$1/ffprobe" -version >/dev/null 2>&1
}
fetch_zip() {  # fetch_zip <url> <programme>
  rm -rf "$TMP/$2" "$TMP/$2.zip"
  curl -fsSL "$1" -o "$TMP/$2.zip" || return 1
  mkdir -p "$TMP/$2" && unzip -oq "$TMP/$2.zip" -d "$TMP/$2" || return 1
  local found
  found="$(find "$TMP/$2" -type f -name "$2" | head -1)"
  [ -n "$found" ] || return 1
  cp "$found" "$DEST/bin/$2" && chmod +x "$DEST/bin/$2"
}
if ffmpeg_ok "$DEST/bin"; then
  echo "ffmpeg déjà présent."
elif [ -z "${KROKCUT_FORCE_FFMPEG_DOWNLOAD:-}" ] && command -v ffmpeg >/dev/null && command -v ffprobe >/dev/null \
     && ffmpeg_ok "$(dirname "$(command -v ffmpeg)")"; then
  ln -sf "$(command -v ffmpeg)" "$DEST/bin/ffmpeg"
  ln -sf "$(command -v ffprobe)" "$DEST/bin/ffprobe"
  echo "ffmpeg du système utilisé."
elif [ "$OS" = "Darwin" ]; then
  rm -f "$DEST/bin/ffmpeg" "$DEST/bin/ffprobe"
  MR_ARCH="arm64"
  [ "$ARCH" = "x86_64" ] && MR_ARCH="amd64"
  for prog in ffmpeg ffprobe; do
    fetch_zip "https://ffmpeg.martin-riedl.de/redirect/latest/macos/$MR_ARCH/release/$prog.zip" "$prog" \
      || { [ "$prog" = ffmpeg ] && fetch_zip "https://evermeet.cx/ffmpeg/getrelease/zip" ffmpeg; } \
      || { [ "$prog" = ffprobe ] && fetch_zip "https://evermeet.cx/ffmpeg/getrelease/ffprobe/zip" ffprobe; } \
      || true
  done
  if ! ffmpeg_ok "$DEST/bin" && command -v brew >/dev/null; then
    echo "Téléchargement direct impossible, installation via Homebrew…"
    brew install ffmpeg && ln -sf "$(brew --prefix)/bin/ffmpeg" "$DEST/bin/ffmpeg" && ln -sf "$(brew --prefix)/bin/ffprobe" "$DEST/bin/ffprobe"
  fi
fi
ffmpeg_ok "$DEST/bin" || fail "ffmpeg n'a pas pu être installé. Installe Homebrew (https://brew.sh) puis relance cette commande."
"$DEST/bin/ffmpeg" -version 2>/dev/null | sed -n 1p

# ----------------------------------------------------------- 4. l'app KrokCut
step "4/4 Création de l'app KrokCut"
chmod +x "$DEST/lancer-mac.sh" "$DEST/lancer.sh" "$DEST/installer.sh" "$DEST/KrokCut.command" 2>/dev/null || true
if [ "$OS" = "Darwin" ]; then
  mkdir -p "$APPS"
  rm -rf "$APPS/KrokCut.app"
  # Petite app AppleScript : lance le serveur en arrière-plan et ouvre le navigateur
  osacompile -o "$APPS/KrokCut.app" -e "do shell script quoted form of \"$DEST/lancer-mac.sh\""
  if [ -d "$HOME/Desktop" ] && [ ! -e "$HOME/Desktop/KrokCut" ]; then
    ln -s "$APPS/KrokCut.app" "$HOME/Desktop/KrokCut" 2>/dev/null || true
  fi
  echo "App créée : $APPS/KrokCut.app (et un raccourci sur le Bureau)."
fi

printf '\n\033[1;32m✔ KrokCut est installé dans %s\033[0m\n' "$DEST"
echo "  Pour l'ouvrir : double-clic sur « KrokCut » (Bureau, Applications ou Launchpad)."
echo "  Pour mettre à jour : relance simplement la même commande."
if [ "$OS" = "Darwin" ] && [ -z "${KROKCUT_NO_OPEN:-}" ]; then
  open "$APPS/KrokCut.app"
fi
