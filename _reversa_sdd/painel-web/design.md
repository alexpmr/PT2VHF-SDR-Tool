# Painel web, Design Técnico

## Interface

| Método | Caminho | Entrada | Saída | Status codes |
|--------|---------|---------|-------|--------------|
| GET | `/` | `key` opcional | HTML (`PAGE`) | 200, 403 |
| GET | `/state` | `key` ou cookie | JSON do estado | 200, 403 |
| GET | `/spectrum` | `key` ou cookie | `{c, fs, db[]}` | 200, 204, 403 |
| GET | `/audio` | `key` ou cookie | stream chunked s16le 16 kHz | 200, 403 |
| GET | outros | — | `404` | 404, 403 |

Contrato completo em [contracts.md](contracts.md) e [openapi/painel-web.yaml](../openapi/painel-web.yaml).

| Símbolo | Assinatura | Retorno | Observação |
|---------|-----------|---------|------------|
| `WebServer` | `(state_fn, spectrum_fn, lan=False, port=8095, require_key=True)` | — | `start`, `stop`, `url(for_lan=None)`, `running`, `key`, `audio`, `error` |
| `AudioHub` | `()` | — | `push(audio48)`, `subscribe()`, `unsubscribe(q)`, `listeners` |
| `is_private_lan` | `(addr)` | `bool` | |
| `detect_lan_ipv4` | `()` | `str` | Socket UDP sem enviar pacote |

## Fluxo Principal
1. Ligar o painel cria `WebServer` com a configuração e registra `web.audio.push` em `engine.audio_listeners`. 🟢
2. O tick atualiza `_web_state` (dict pronto); as threads HTTP só leem. 🟢
3. Cada requisição passa por `_authorized` e é roteada. 🟢
4. `/audio` assina o hub e escreve chunks até o servidor parar ou o cliente cair. 🟢

## Fluxos Alternativos
- **Porta ocupada:** "Não foi possível abrir a porta N: <erro>". 🟢 `ui/main_window.py:1571-1572`
- **Cookie malformado:** acesso negado. 🟢
- **Desligar:** remove o ouvinte do hub e para o servidor. 🟢

## Dependências
`http.server`, `secrets`, `hmac`, `ipaddress`, `dsp.filters.Decimator`. 🟢

## Decisões de Design Identificadas

| Decisão | Evidência no código | Confiança |
|---------|---------------------|-----------|
| Local/LAN com chave; IP privado sem chave opcional (ADR 008) | `webserver.py:142-163` | 🟢 |
| Somente leitura | `webserver.py:4` | 🟢 |
| Encerramento síncrono (8f3d331) | `webserver.py:242-260` | 🟢 |

## Estado Interno
`_httpd`, `_thread`, `key`, `lan`, `port`, `require_key`, hub com filas por ouvinte; UI `_web_state`, `_web_aprs`. 🟢

## Observabilidade
`log_message` silenciado; status no painel de configurações; `listeners` no `/state`. 🟢

## Riscos e Lacunas
- 🟡 Sem TLS: chave em claro na LAN.
- 🟡 Sem limite de tentativas de chave.
- 🔴 Sem teste que garanta a ausência de rotas de escrita no futuro.
