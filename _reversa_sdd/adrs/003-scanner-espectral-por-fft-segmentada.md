# ADR 003: Scanner espectral por fft segmentada

- **Status:** Aceito (retroativo)
- **Data/origem:** 2026-11-07 (v0.2.0)

## Contexto
Varrer memória por memória é lento; o operador queria descobrir atividade numa faixa larga.

## Decisão
Scanner por FFT: o centro do SDR salta em segmentos (80% da taxa útil), espera `settle_lines`, acumula `dwell_lines` com max-hold, ignora o pico de DC e trata acertos acima de piso+SNR. Há canal prioritário, lockouts e escuta com retomada após `resume_s` sem atividade ou `max_listen_s`.

## Evidência
🟢 `pt2vhf/scanner.py:145-360`; CHANGELOG 0.2.0 (~640 canais/s a 1,2 MS/s).

## Consequências
Rápido e sem retunes por canal; detecta ocupação, não mede continuamente (ocupação 24 h conta detecções, v0.7.0).
