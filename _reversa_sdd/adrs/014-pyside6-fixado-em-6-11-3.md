# ADR 014: Pyside6 fixado em 6 11 3

- **Status:** Aceito (retroativo)
- **Data/origem:** 2026-11-08 (7d44328)

## Contexto
Versões mais novas do PySide6 causavam crash no encerramento (CI e distribuição).

## Decisão
Fixar PySide6 6.11.3 no `pyproject.toml`, CI e empacotamento; `scripts/run_tests.py` evita segfault Qt após o teardown.

## Evidência
🟢 commit 7d44328; `pyproject.toml`; CLAUDE.md.

## Consequências
Estabilidade; atualizar Qt exige revalidar o shutdown.
