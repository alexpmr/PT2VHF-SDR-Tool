# CAT · Hamlib rigctld, Contratos

Protocolo de texto do `rigctld` (Hamlib), modo curto, uma linha por comando, terminador `\n`, ASCII estrito. O programa é cliente TCP. 🟢 `pt2vhf/rigctl.py`

| Comando enviado | Resposta esperada | Uso |
|---|---|---|
| `f` | `<hz>` (1 linha) | Ler frequência |
| `m` | `<modo>` e `<passband>` (2 linhas) | Ler modo |
| `F <hz inteiro>` | `RPRT 0` | Definir frequência |
| `M <modo> 0` | `RPRT 0` | Definir modo, passband padrão |

Regras:
- Linha com CR/LF ou acima de 160 caracteres é recusada antes de conectar.
- Até 5 linhas lidas por comando; `RPRT -N` em qualquer linha = `RigCtlError("Hamlib: …")`; nenhuma linha = "Sem resposta do rigctld".
- Frequência lida não numérica = "Resposta de frequência inválida"; fora de 1 kHz–10 GHz = "Frequência CAT fora do intervalo".

## Mapa de modos
| SDR | Hamlib (envio) | Hamlib (leitura) → SDR |
|---|---|---|
| NFM | FM | FM, FMN → NFM |
| WFM | WFM | WFM |
| AM, USB, LSB, CW, DSB | iguais | iguais; CWR → CW |
| outros | erro | texto vazio (modo não muda) |

Comandos **proibidos** por política: `T` (PTT) e qualquer outro de transmissão. 🟢
