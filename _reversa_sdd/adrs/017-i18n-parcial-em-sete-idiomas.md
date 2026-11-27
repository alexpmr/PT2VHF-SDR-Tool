# ADR 017: I18n parcial em sete idiomas

- **Status:** Aceito (retroativo)
- **Data/origem:** 2026-11-08 (v0.9.0)

## Contexto
Público internacional de radioamadores.

## Decisão
`pt2vhf/i18n.py` com 7 idiomas e tradução parcial; textos-chave traduzidos, o resto cai no português.

## Evidência
🟢 CHANGELOG 0.9.0; 🟡 cobertura exata não medida.

## Consequências
Mistura de idiomas na UI; código que depende de textos PT-BR fica frágil.
