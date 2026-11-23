#!/usr/bin/env bash
# Prepara o AIS-catcher (jvde-github, GPL-3.0) embarcado no PT2VHF SDR Tool.
#
# Uso: packaging/prepare_ais_catcher.sh [windows|native] [saida]
#   windows (padrão): baixa o pacote oficial x64 da release fixada e confere SHA-256
#   native: compila a mesma tag a partir do código-fonte (testes Linux/macOS)
#
# Em ambos os casos o código-fonte correspondente (git archive do commit
# fixado, conferido pelo hash do commit) e os avisos de licença vão para
# <saida>, cumprindo a GPL-3.0.
set -euo pipefail

TARGET="${1:-windows}"
OUT="${2:-packaging/ais_catcher}"
mkdir -p "$OUT"; OUT="$(cd "$OUT" && pwd)"
TAG="v0.71"
COMMIT="a3cb3bf8f30b462dff58c9b874dd9d932b45406a"
BIN_URL="https://github.com/jvde-github/AIS-catcher/releases/download/$TAG/AIS-catcher.x64.zip"
BIN_SHA256="204f1902a352e7badbbdb72e7ee4ca331d322dcfe2bacf0ccb20c87db1a88b5b"
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

check() {  # arquivo sha256
  local got
  got="$(sha256sum "$1" | cut -d' ' -f1)"
  [ "$got" = "$2" ] || { echo "SHA-256 inválido para $1: $got" >&2; exit 1; }
}

rm -rf "$OUT"; mkdir -p "$OUT/source"
git -c advice.detachedHead=false clone --quiet --depth 1 --branch "$TAG" \
  https://github.com/jvde-github/AIS-catcher.git "$WORK/ais"
[ "$(git -C "$WORK/ais" rev-parse HEAD)" = "$COMMIT" ] || { echo "commit inesperado" >&2; exit 1; }
git -C "$WORK/ais" archive --format=zip --prefix="AIS-catcher-${TAG#v}/" \
  -o "$OUT/source/AIS-catcher-${TAG#v}-source.zip" HEAD

case "$TARGET" in
  windows)
    curl -fsSL --retry 3 -o "$WORK/bin.zip" "$BIN_URL"
    check "$WORK/bin.zip" "$BIN_SHA256"
    python -I -c "import sys, zipfile; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" \
      "$WORK/bin.zip" "$OUT" 2>/dev/null \
      || python3 -I -c "import sys, zipfile; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" \
      "$WORK/bin.zip" "$OUT"
    rm -f "$OUT/start.bat" "$OUT/start-GUI.bat"
    [ -f "$OUT/AIS-catcher.exe" ] || { echo "AIS-catcher.exe ausente no pacote" >&2; exit 1; }
    ;;
  native)
    cmake -S "$WORK/ais" -B "$WORK/build" -DCMAKE_BUILD_TYPE=Release >/dev/null
    cmake --build "$WORK/build" -j "$(nproc 2>/dev/null || echo 2)" >/dev/null
    cp "$WORK/build/AIS-catcher" "$OUT/"
    mkdir -p "$OUT/Licenses"; cp "$WORK/ais/LICENSE" "$OUT/Licenses/AIS-catcher"
    ;;
  *) echo "alvo inválido: $TARGET" >&2; exit 2 ;;
esac

cp "$HERE/sonde_licenses/README-AIS-CATCHER.txt" "$OUT/README-THIRD-PARTY.txt"
echo "$TAG $COMMIT" > "$OUT/SOURCE_COMMIT.txt"
(cd "$OUT" && sha256sum AIS-catcher* | tee SHA256SUMS.txt)
