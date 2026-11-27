# ADR 004: Assistente de sintonia atua no vfo

- **Status:** Aceito (retroativo)
- **Data/origem:** 2026-11-07 (v0.3.0)

## Contexto
Corrigir desvio de frequência no áudio (deslocamento de pitch) distorce o sinal e confunde o operador.

## Decisão
O assistente mede o desvio do sinal e corrige a frequência do VFO; o áudio nunca é deslocado artificialmente.

## Evidência
🟢 CHANGELOG 0.3.0; 🟡 confirmação por leitura parcial de `ui/assist_panels.py`.

## Consequências
Frequência exibida reflete a real; correção depende do VFO aceitar o retune.
