/* PT2VHF SDR Tool: força stdin/stdout em modo binário no Windows.
 *
 * fsk_demod/rs41mod foram escritos para pipes POSIX. No Windows (MSVCRT),
 * stdin/stdout abrem em modo texto: 0x1A encerra a leitura e \n vira \r\n,
 * corrompendo IQ int16 e bits suaves. Este construtor roda antes de main()
 * sem alterar o código-fonte original dos decodificadores.
 * Licença: mesma do programa ao qual é ligado (LGPL-2.1 / GPL-3.0). */
#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#include <stdio.h>

__attribute__((constructor)) static void pt2vhf_binary_stdio(void)
{
    _setmode(_fileno(stdin), _O_BINARY);
    _setmode(_fileno(stdout), _O_BINARY);
}
#endif
