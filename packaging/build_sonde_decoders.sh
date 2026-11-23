#!/usr/bin/env bash
# Compila fsk_demod (codec2, LGPL-2.1) e rs41mod (rs1729/radiosonde_auto_rx,
# GPL-3.0) para embarcar no Setup/Portable do PT2VHF SDR Tool.
#
# Uso:  packaging/build_sonde_decoders.sh [windows|native] [saida]
#   windows (padrão): compilação cruzada estática com x86_64-w64-mingw32-gcc
#   native: compila para o sistema atual (testes Linux/macOS)
#
# Fonte fixada por commit (reprodutível). O código-fonte correspondente usado
# é copiado para <saida>/source junto com os textos de licença, cumprindo a
# GPL-3.0/LGPL-2.1 na distribuição dos binários.
set -euo pipefail
# ${EXTRA[@]+...}: compatível com o bash 3.2 do macOS (array vazio + set -u).

TARGET="${1:-windows}"
OUT="${2:-packaging/sonde_decoders}"
AUTORX_REPO="https://github.com/projecthorus/radiosonde_auto_rx.git"
AUTORX_COMMIT="53d03c72ad18ce4357c0cedd1f4acf2bf1efb36e"
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

case "$TARGET" in
  windows) CC="${CC:-x86_64-w64-mingw32-gcc}"; EXE=".exe"
           EXTRA=(-static -DCYGWIN "$HERE/sonde_win_binary_io.c") ;;
  native)  CC="${CC:-cc}"; EXE=""; EXTRA=() ;;
  *) echo "alvo inválido: $TARGET" >&2; exit 2 ;;
esac
command -v "$CC" >/dev/null || { echo "compilador ausente: $CC" >&2; exit 1; }

git -c advice.detachedHead=false clone --quiet "$AUTORX_REPO" "$WORK/src"
git -C "$WORK/src" checkout --quiet "$AUTORX_COMMIT"
U="$WORK/src/utils"; M="$WORK/src/demod/mod"

mkdir -p "$OUT"
CFLAGS=(-O2 -Wall -Wno-unused -Wno-unused-result)
"$CC" "${CFLAGS[@]}" -o "$OUT/fsk_demod$EXE" \
  "$U/fsk_demod.c" "$U/fsk.c" "$U/modem_stats.c" "$U/kiss_fftr.c" "$U/kiss_fft.c" \
  ${EXTRA[@]+"${EXTRA[@]}"} -lm
"$CC" "${CFLAGS[@]}" -o "$OUT/rs41mod$EXE" \
  "$M/rs41mod.c" "$M/bch_ecc_mod.c" "$M/demod_mod.c" ${EXTRA[@]+"${EXTRA[@]}"} -lm

# Fonte correspondente + licenças (obrigatório para redistribuir binários GPL/LGPL).
SRC="$OUT/source"
rm -rf "$SRC"; mkdir -p "$SRC/utils" "$SRC/demod/mod"
cp "$U"/{fsk_demod.c,fsk.c,fsk.h,modem_stats.c,modem_stats.h,kiss_fft.c,kiss_fft.h,kiss_fftr.c,kiss_fftr.h,_kiss_fft_guts.h,comp.h,comp_prim.h,codec2_fdmdv.h,modem_probe.h,Makefile} "$SRC/utils/"
cp "$M"/{rs41mod.c,bch_ecc_mod.c,bch_ecc_mod.h,demod_mod.c,demod_mod.h,Makefile} "$SRC/demod/mod/"
cp "$HERE/sonde_win_binary_io.c" "$HERE/build_sonde_decoders.sh" "$SRC/"
cp "$WORK/src/LICENSE" "$OUT/LICENSE-GPL-3.0.txt"
cp "$HERE/sonde_licenses/LICENSE-LGPL-2.1.txt" "$OUT/LICENSE-LGPL-2.1.txt"
cp "$HERE/sonde_licenses/README-THIRD-PARTY.txt" "$OUT/README-THIRD-PARTY.txt"
echo "$AUTORX_COMMIT" > "$OUT/SOURCE_COMMIT.txt"
(cd "$OUT" && sha256sum "fsk_demod$EXE" "rs41mod$EXE" | tee SHA256SUMS.txt)
