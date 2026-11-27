# ADR 005: Timeshift em buffer iq int8

- **Status:** Aceito (retroativo)
- **Data/origem:** 2026-11-07 (v0.3.0)

## Contexto
O operador quer voltar alguns segundos e reouvir uma transmissão, sem gastar muita memória.

## Decisão
Buffer circular de IQ (`TimeShiftBuffer`), padrão 20 s, quantizado em int8 com o centro de cada trecho. Em replay a engine lê do buffer em vez do bloco ao vivo e volta ao vivo sozinha quando alcança o presente.

## Evidência
🟢 `pt2vhf/timeshift.py:17,36`; `pt2vhf/engine.py:62-64,236-269,360-367`.

## Consequências
Memória baixa (2 bytes por amostra); a quantização int8 reduz a faixa dinâmica do replay frente ao ao vivo.
