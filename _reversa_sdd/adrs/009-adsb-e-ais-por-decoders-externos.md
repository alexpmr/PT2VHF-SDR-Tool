# ADR 009: Adsb e ais por decoders externos

- **Status:** Aceito (retroativo)
- **Data/origem:** 2026-11-08 (v0.8.0)

## Contexto
Demodular ADS-B (1090 MHz, 2 MS/s+) e AIS dentro do app exigiria outro SDR ou modo dedicado.

## Decisão
ADS-B, AIS e sondas entram por arquivos/feeds de decoders externos (dump1090/readsb, NMEA AIS); o app só lê, mapeia e exibe telemetria.

## Evidência
🟢 CHANGELOG 0.8.0; `pt2vhf/traffic.py`; CLAUDE.md (não alegar demodulação RF nativa).

## Consequências
Sem demodulação nativa; depende do operador rodar decoders externos. O backlog de 23/11 (v1.0.7) cita modos embarcados, não presentes nesta branch 🟡.
