# ADR 001: Controle do dongle por fila com watchdog

- **Status:** Aceito (retroativo)
- **Data/origem:** 2026-11-07 (v0.4.0; 13dc4da em 2026-11-08)

## Contexto
Com o RTL-SDR Blog V4, a troca de faixa congelava a interface porque a thread Qt chamava o driver diretamente e a chamada podia nunca retornar.

## Decisão
A UI nunca fala com o dongle. Comandos (frequência, ganho, PPM, bias-T, amostragem direta) vão para uma fila de controle com timeout (`CMD_TIMEOUT_S`). Um vigia (`_watch_loop`) detecta comando travado ou ausência de amostras (`STALL_S`), reconecta até `MAX_RECOVER` vezes e marca `status` ok/recovering/failed. Frequências fora da faixa são recusadas antes de chegar ao driver.

## Evidência
🟢 `pt2vhf/sources/rtlsdr_source.py:183,478-503`; CHANGELOG 0.4.0; commit 13dc4da (threads órfãs após recuperação).

## Consequências
UI responsiva mesmo com driver travado; porém o contrato de erro de `set_center_freq` ficou inconsistente entre fontes (RTL devolve False, rtl_tcp/Soapy levantam `SourceError`), e só o caso False é tratado em `engine._retune` (ver code-analysis.md, achado 1).
