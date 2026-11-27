# ADR 002: Driver rtl sdr blog com fallback

- **Status:** Aceito (retroativo)
- **Data/origem:** 2026-11-07 (v0.4.1, v0.5.0; 7ff7f74)

## Contexto
O V4 precisa da biblioteca do RTL-SDR Blog, mas a DLL Blog não exporta algumas funções (dithering) e a chamada ausente deixava o dongle preso (ACCESS).

## Decisão
Empacotar a biblioteca Blog como padrão, com stubs para funções ausentes e opção `rtl_library` para voltar à biblioteca padrão do librtlsdr.

## Evidência
🟢 commit 7ff7f74 e c6232f0; CHANGELOG 0.4.1/0.5.0. 🟡 seleção exata da DLL em tempo de execução inferida de `sources/`.

## Consequências
Suporte ao V4 sem exigir instalação manual; dependência de binários nativos embarcados que precisam ser auditados a cada atualização.
