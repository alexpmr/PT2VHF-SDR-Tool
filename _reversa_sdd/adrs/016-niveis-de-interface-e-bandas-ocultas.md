# ADR 016: Niveis de interface e bandas ocultas

- **Status:** Aceito (retroativo)
- **Data/origem:** 2026-11-08 (v0.6.0), revisto em 2026-11-09 (v0.13.0)

## Contexto
Iniciantes se perdiam com muitos controles e bandas que o hardware não sintoniza.

## Decisão
Níveis Essencial/Intermediário/Avançado escondem abas e grupos, sem apagar configurações. Bandas incompatíveis com a fonte, antes esmaecidas (v0.6.0), passaram a ser ocultadas (v0.13.0).

## Evidência
🟢 `pt2vhf/ui/main_window.py:2282-2300,957`; CHANGELOG 0.6.0/0.13.0. 🟡 `apply_level` casa títulos de grupo em português (achado 6).

## Consequências
Interface mais limpa; os níveis não são controle de acesso.
