# ADR 015: Build windows sob demanda

- **Status:** Aceito (retroativo)
- **Data/origem:** 2026-11-07 (bbea710)

## Contexto
Cada push gerava build Windows caro e podia criar release sem querer.

## Decisão
`build.yml` roda testes Linux offscreen em push/PR; o job Windows só roda por despacho manual (`build_windows=true`) ou commit com `[build-windows]`, que em `main` pode criar Release. Promoção e verificação do site são workflows manuais separados.

## Evidência
🟢 commit bbea710; `.github/workflows/build.yml`, `release.yml`, `verify-site.yml`.

## Consequências
Economia de CI; exige disciplina com o marcador `[build-windows]`.
