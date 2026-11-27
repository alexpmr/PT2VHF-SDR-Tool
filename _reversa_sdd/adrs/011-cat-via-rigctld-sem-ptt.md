# ADR 011: Cat via rigctld sem ptt

- **Status:** Aceito (retroativo)
- **Data/origem:** 2026-11-08 (v0.8.0)

## Contexto
Integrar com programas de rádio (logs, rotores) sem risco de transmitir.

## Decisão
Cliente TCP do Hamlib `rigctld` com conjunto restrito de comandos (`f`, `m`, `F`, `M`); nenhum comando de PTT/transmissão; frequência validada.

## Evidência
🟢 `pt2vhf/rigctl.py:1-80`; CHANGELOG 0.8.0.

## Consequências
Seguro para um receptor; requer `rigctld` externo.
