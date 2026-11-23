Decodificadores de radiossonda embarcados no PT2VHF SDR Tool
============================================================

Estes programas são de terceiros, distribuídos sem modificação funcional,
como executáveis separados chamados por pipe (stdin/stdout). Não são parte
do código do PT2VHF SDR Tool.

fsk_demod
  Origem: projeto codec2 (David Rowe, Brady O'Brien), cópia mantida em
          radiosonde_auto_rx/utils.
  Licença: GNU Lesser General Public License v2.1 (LICENSE-LGPL-2.1.txt).

rs41mod
  Origem: rs1729/RS (zilog80), cópia mantida em radiosonde_auto_rx/demod/mod.
  Licença: GNU General Public License v3.0 (LICENSE-GPL-3.0.txt).

Fonte: https://github.com/projecthorus/radiosonde_auto_rx
Commit: ver SOURCE_COMMIT.txt

O código-fonte correspondente exato usado na compilação está na pasta
"source" ao lado destes arquivos, incluindo o script de build
(build_sonde_decoders.sh) e o único arquivo adicional ligado aos
executáveis Windows (sonde_win_binary_io.c, que coloca stdin/stdout em modo
binário). Compilado com x86_64-w64-mingw32-gcc, ligação estática.

Você pode redistribuir e modificar estes programas nos termos das licenças
acima. Eles são fornecidos SEM QUALQUER GARANTIA.
