# ADR 008: Painel web local e lan com chave

- **Status:** Aceito (retroativo)
- **Data/origem:** 2026-11-07 (v0.4.0, v0.5.0); 8f3d331 em 2026-11-08

## Contexto
Ouvir o receptor de outro dispositivo da casa sem expor o programa à Internet.

## Decisão
Servidor HTTP somente leitura (`/`, `/state`, `/spectrum`, `/audio`). Loopback sempre autorizado; LAN só se habilitada; IP privado pode dispensar chave conforme `web_require_key`; caso contrário chave por query/cookie comparada com `hmac.compare_digest`. Dados APRS não confiáveis são escapados.

## Evidência
🟢 `pt2vhf/webserver.py:85-160`; `pt2vhf/config.py:87`; CHANGELOG 0.4.0/0.5.0; commit 8f3d331.

## Consequências
Conveniente na LAN; sem TLS nem autenticação forte; o default de `WebServer(require_key=True)` diverge do default de config (`False`), ver code-analysis.md achado 7.
