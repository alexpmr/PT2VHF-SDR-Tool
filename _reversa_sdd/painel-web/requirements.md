# Painel web

## Visão Geral
Servidor HTTP embutido que replica a sessão no navegador (LCD, espectro, APRS recebido) e transmite o áudio, no próprio computador ou na rede local. **Somente leitura:** o navegador não muda frequência, modo nem nada no rádio. Desligado por padrão. 🟢

## Responsabilidades
- Servir a página, o estado em JSON, o espectro reduzido e o áudio PCM. 🟢
- Autorizar por origem (loopback, LAN privada, chave). 🟢
- Distribuir o áudio a vários ouvintes sem bloquear a DSP. 🟢
- Abrir e copiar o endereço de acesso. 🟢

## Regras de Negócio
- Desligado por padrão (`web_enabled = False`); porta padrão 8095 (1024–65535). 🟢 `ui/settings_panel.py:105-112`
- Sem LAN, escuta só em `127.0.0.1`; com LAN, em `0.0.0.0`. 🟢 `webserver.py:236`
- Autorização (ver `permissions.md` §2): loopback sempre; sem LAN, recusa outros; LAN com chave dispensada aceita IP privado (10/8, 172.16/12, 192.168/16, link-local, fc00::/7, inclusive IPv4 mapeado); caso contrário exige `?key=` ou cookie `PT2VHFSDR`, comparados com `hmac.compare_digest`. 🟢 `webserver.py:85-163`
- Chave nova a cada início do servidor (`secrets.token_urlsafe(24)`); com chave válida o servidor grava cookie `HttpOnly; SameSite=Strict; Path=/`. 🟢 `webserver.py:107,155-156`
- O valor efetivo de "exigir chave" vem da configuração (`web_require_key`, padrão False); o default `True` do construtor `WebServer` não é usado pela UI. 🟢 `ui/main_window.py:1565-1568`. 🟡 Dívida D7 é só de leitura do código.
- Acesso negado: 403 "Acesso negado: use o endereço com a chave copiado no PT2VHF SDR Tool." 🟢 `webserver.py:167-170`
- Só GET; rota desconhecida = 404. 🟢 `webserver.py:164-191`
- Respostas com `Cache-Control: no-store` e `X-Content-Type-Options: nosniff`. 🟢 `webserver.py:131-134`
- `/spectrum` reduz por máximo a até ~1024 pontos, arredondados a 0,1 dB; sem espectro = 204. 🟢 `webserver.py:177-187`
- Áudio: 48 → 16 kHz, PCM s16le mono, chunked, cabeçalho `X-Audio-Format: s16le;rate=16000;channels=1`; fila de 40 blocos por ouvinte com descarte do mais antigo; sem áudio por 1 s envia 100 ms de silêncio para manter a conexão. 🟢 `webserver.py:37-82,193-212`
- O áudio da web é o áudio tratado (depois de squelch e volume), e continua tocando no computador. 🟢 `ui/main_window.py:1575`
- Estado publicado: versão, frequência, modo, largura, S, dBm, squelch, CTCSS, memória, flags SCAN e REPLAY, receptor ligado, últimos pacotes APRS e número de ouvintes. 🟢 `ui/main_window.py:1599-1609`
- As threads HTTP só leem dados prontos; nunca tocam o Qt nem o rádio. 🟢 `webserver.py:99-102`
- Encerramento síncrono: `stop()` fecha o socket e junta a thread; não pode ser chamado da thread HTTP. 🟢 `webserver.py:242-260`, commit 8f3d331
- HTTP sem TLS; não expor à Internet. 🟢 `webserver.py:6`, CLAUDE.md

## Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-01 | Página com LCD, espectro e APRS | Should | `/` devolve HTML |
| RF-02 | Estado JSON | Should | `/state` com os campos listados |
| RF-03 | Espectro JSON | Should | `/spectrum` com `c`, `fs`, `db` |
| RF-04 | Áudio ao vivo | Should | `/audio` chunked s16le 16 kHz |
| RF-05 | Controle de acesso | Must | Matriz de `permissions.md` |
| RF-06 | Somente leitura | Must | Nenhuma rota altera o rádio |
| RF-07 | Abrir e copiar endereço | Should | URL com chave quando exigida |

## Requisitos Não Funcionais

| Tipo | Requisito inferido | Evidência no código | Confiança |
|------|--------------------|---------------------|-----------|
| Segurança | Comparação de chave em tempo constante | `webserver.py:154,163` | 🟢 |
| Segurança | Cookie HttpOnly, SameSite=Strict | `webserver.py:156` | 🟢 |
| Segurança | Sem TLS nem limite de tentativas | `webserver.py` | 🟡 |
| Performance | ~32 kB/s por ouvinte | `webserver.py:5` | 🟢 |
| Responsividade | Ouvinte lento não atrasa os outros | `webserver.py:50-58` | 🟢 |

## Critérios de Aceitação

```gherkin
Dado o painel web ligado sem LAN
Quando um navegador em 127.0.0.1 abre /
Então recebe a página

Dado LAN ligada com chave exigida
Quando 192.168.0.20 abre / sem chave
Então recebe 403

Dado LAN ligada com chave exigida
Quando 192.168.0.20 abre /?key=<chave>
Então recebe a página e o cookie PT2VHFSDR

Dado LAN ligada sem chave
Quando 192.168.0.20 abre /
Então recebe a página

Dado LAN ligada sem chave
Quando 8.8.4.4 abre / sem chave
Então recebe 403

Dado qualquer cliente autorizado
Quando faz GET /tune
Então recebe 404
```

## Prioridade (MoSCoW)

| Requisito | MoSCoW | Justificativa |
|-----------|--------|---------------|
| Acesso e somente leitura | Must | Segurança |
| Página, estado, espectro, áudio | Should | Recurso opcional |

## Rastreabilidade de Código

| Arquivo | Função / Classe | Cobertura |
|---------|-----------------|-----------|
| `pt2vhf/webserver.py` | `WebServer`, `AudioHub`, `is_private_lan`, `detect_lan_ipv4`, `PAGE`, `AUDIO_RATE_OUT` | 🟢 |
| `pt2vhf/ui/main_window.py` | `_toggle_web`, `_web_open`, `_web_copy`, `_update_web_state`, `_web_aprs` | 🟢 |
| `pt2vhf/ui/settings_panel.py` | grupo da interface web | 🟢 |
