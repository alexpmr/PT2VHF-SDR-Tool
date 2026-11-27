# Painel web, Tarefas de Implementação

## Pré-requisitos
- [ ] Engine com `audio_listeners`, `spectrum`, `spectrum_center`
- [ ] Estado da UI calculado no tick

## Tarefas

- [ ] T-01, `is_private_lan` e autorização
  - Origem no legado: `pt2vhf/webserver.py:85-163`
  - Critério de pronto: matriz de `contracts.md` coberta por testes
  - Confiança: 🟢
- [ ] T-02, Rotas `/`, `/state`, `/spectrum`, 404
  - Origem no legado: `pt2vhf/webserver.py:164-191`
  - Critério de pronto: códigos e formatos de `contracts.md`
  - Confiança: 🟢
- [ ] T-03, `AudioHub` e `/audio` chunked
  - Origem no legado: `pt2vhf/webserver.py:37-82,193-212`
  - Critério de pronto: ouvinte lento descarta sem afetar os outros
  - Confiança: 🟢
- [ ] T-04, `start`/`stop` síncronos
  - Origem no legado: `pt2vhf/webserver.py:236-260`
  - Critério de pronto: sem thread viva após `stop`
  - Confiança: 🟢
- [ ] T-05, Página `PAGE` com escape de dados APRS
  - Origem no legado: `pt2vhf/webserver.py:263-`, commit 8f3d331
  - Critério de pronto: texto com `<script>` aparece escapado
  - Confiança: 🟢
- [ ] T-06, Integração na UI e configurações
  - Origem no legado: `pt2vhf/ui/main_window.py:1550-1610`, `ui/settings_panel.py:104-125`
  - Critério de pronto: chave só aparece na URL quando exigida
  - Confiança: 🟢
- [ ] T-07, Teste que proíbe métodos e rotas de escrita
  - Origem no legado: lacuna
  - Critério de pronto: POST/PUT/DELETE recusados
  - Confiança: 🟡

## Tarefas de Teste

- [ ] TT-01, Autorização e rotas (`tests/test_webserver.py`)
- [ ] TT-02, Áudio chunked
- [ ] TT-03, Escape de APRS

## Ordem Sugerida
1. T-01 e T-04.
2. T-02 e T-03.
3. T-05 e T-06.
4. T-07.

## Lacunas Pendentes (🔴)
- Decidir se a LAN deve ter TLS ou limite de tentativas.
