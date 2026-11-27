# ADR 010: Rs41 do mesmo iq com binarios externos

- **Status:** Aceito (retroativo)
- **Data/origem:** 2026-11-08 (v0.9.0; correção fa10118 na v0.11.0)

## Contexto
Decodificar radiossondas RS41 sem um segundo dongle.

## Decisão
`RS41Receiver` reaproveita o IQ já capturado, converte o canal para 48 kS/s centrado em 0 Hz (banda base, para casar com a máscara ±5 kHz do `fsk_demod`) e alimenta `fsk_demod` | `rs41mod` por pipes, com diagnóstico e captura IQ opcional.

## Evidência
🟢 `pt2vhf/sonde_rx.py:113-330`; commit fa10118. 🟡 docstring ainda fala em FI +12 kHz (achado 4).

## Consequências
Um SDR só; mas RS41 é 🔴 P0 aberto: sem prova com RF real de serial/posição/altitude.
