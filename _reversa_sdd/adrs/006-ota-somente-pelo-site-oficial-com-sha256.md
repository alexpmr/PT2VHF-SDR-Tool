# ADR 006: Ota somente pelo site oficial com sha256

- **Status:** Aceito (retroativo)
- **Data/origem:** 2026-11-07 (v0.3.0), endurecido em 2026-11-10 (v0.13.1, 7566c5e)

## Contexto
Atualização automática é um vetor de ataque; o site PT2VHF publica os pacotes.

## Decisão
OTA só aceita manifesto `schema=1` do produto `sdr`, URL HTTPS no host oficial (caminho de download ou `download.php` com query exata), nome `.exe` restrito, tamanho até `MAX_PACKAGE_BYTES` e SHA-256 obrigatório. Redirecionamentos só na cadeia permitida. Execução do código-fonte (`source`) nunca se atualiza sozinha; só os executáveis Windows aplicam via auxiliar PowerShell. Sem abrir o navegador como fallback (v0.13.3).

## Evidência
🟢 `pt2vhf/updater.py:64-160,236-256`; commits 7566c5e, 506d0e1, 1080efe; CHANGELOG 0.13.1-0.13.3.

## Consequências
Seguro por padrão; clientes v0.13.0 precisam de atualização manual; OTA ponta a ponta ainda 🔴 não homologada (P0 no BACKLOG).
