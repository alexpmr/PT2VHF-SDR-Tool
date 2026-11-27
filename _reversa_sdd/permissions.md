# Permissões e controle de capacidades — PT2VHF SDR Tool

O PT2VHF SDR Tool é um aplicativo desktop de um único operador. **Não há usuários, papéis nem RBAC** 🟢: quem abre o programa controla tudo. O controle de acesso que existe é por **canal de acesso** (local, LAN, rede externa) e por **capacidade sensível** (transmitir, elevar privilégio, baixar código ou modelos).
Escala: 🟢 confirmado no código · 🟡 inferido · 🔴 lacuna.

## 1. Atores

| Ator | Como chega | Observação |
|---|---|---|
| Operador local | Janela Qt | Acesso total. Pode estar em qualquer nível de interface. |
| Ouvinte local | Navegador em `127.0.0.1` | Painel web, sempre autorizado. |
| Ouvinte na LAN | Navegador em IP privado | Só se o operador habilitar LAN. |
| Cliente externo (Internet) | IP público | Nunca deve ser exposto; só passa com a chave. |
| Software CAT | `rigctld` (TCP 4532) | O app é cliente; só lê e ajusta frequência e modo. |
| Site oficial PT2VHF | HTTPS `www.pt2vhf.com` | Fonte única de atualização. |
| Windows (UAC) | Elevação | Só para trocar driver WinUSB. |

## 2. Matriz de acesso ao painel web 🟢
`pt2vhf/webserver.py:85-160`. Todas as rotas são GET e somente leitura: `/`, `/state`, `/spectrum`, `/audio`. Outras rotas devolvem 404.

| Origem do cliente | LAN desligada | LAN ligada, chave exigida | LAN ligada, chave dispensada |
|---|---|---|---|
| Loopback (127.0.0.1, ::1) | ✅ | ✅ | ✅ |
| IP privado (10/8, 172.16/12, 192.168/16, link-local, fc00::/7) | ❌ | ✅ com `?key=` ou cookie | ✅ sem chave |
| IP público | ❌ | ✅ com `?key=` ou cookie | ✅ com chave apenas |
| Sintonizar, gravar ou mudar configuração | ❌ em todos os casos | ❌ | ❌ |

Regras:
- A chave é comparada com `hmac.compare_digest`. Com chave válida o servidor grava o cookie `PT2VHFSDR` (`HttpOnly`, `SameSite=Strict`).
- 🟡 Não há TLS: a chave trafega em claro na LAN.
- 🟡 O default diverge: `WebServer(require_key=True)` no construtor, mas `web_require_key: False` em `config.py:87`. O comportamento efetivo depende de como a UI instancia o servidor.
- 🟢 Texto APRS de terceiros é escapado antes de ir para a página (commit 8f3d331).

## 3. Capacidades sensíveis

| Capacidade | Disponível? | Quem decide | Controle | Evidência |
|---|---|---|---|---|
| Transmitir RF / PTT | ❌ | Ninguém | Não existe no código; CAT sem comando `T` | 🟢 `rigctl.py:1-3` |
| Enviar dados ao APRS-IS (iGate) | ❌ na UI | — | UI removida na v0.10.0; código órfão exige indicativo e passcode de 1 a 5 dígitos e usa qAO | 🟢 `aprs_igate.py:1-160`, CHANGELOG 0.10.0 |
| Controle CAT | ✅ | Operador | Apenas `f`, `m`, `F`, `M`; frequência validada | 🟢 `rigctl.py:30-80` |
| Elevar privilégio (UAC) | ✅ sob demanda | Operador | Um UAC via `runas` para `wdi-simple`, só na interface 0 | 🟢 `sources/rtl_driver.py:104-125` |
| Atualizar o programa (OTA) | ✅ instalador e portátil; ❌ código-fonte | Operador e política | Host oficial, HTTPS, nome restrito, tamanho e SHA-256; adiada se o programa estiver ocupado | 🟢 `updater.py:64-160`, `ui/main_window.py:1441` |
| Baixar modelos Whisper | ✅ sob ação explícita | Operador | Nada é baixado automaticamente; inferência offline | 🟢 `live_caption.py` |
| Baixar binários RS41 | ❌ | Operador instala manualmente | Caminho informado pelo operador ou PATH | 🟢 `sonde_rx.py:29` |
| Ler feeds ADS-B/AIS | ✅ | Operador | Só arquivos locais; limites de 2 MB (AIS) e 8 MB (JSON) | 🟢 `traffic.py` |
| Gravar áudio e IQ | ✅ | Operador | Pasta local do operador; sem envio externo | 🟢 `audio.py`, `engine.py` |
| Abrir mais de uma instância | ❌ no Windows | Sistema | Mutex `PT2VHF_SDR_Tool_Running` | 🟢 `app.py` |

## 4. Níveis de interface (não são permissões) 🟢
`pt2vhf/ui/main_window.py:2282-2300`

| Página | Essencial | Intermediário | Avançado |
|---|---|---|---|
| Ferramentas | ✅ | ✅ | ✅ |
| Scanner | ❌ oculta | ✅ | ✅ |
| Decodificação | ❌ oculta | ✅ | ✅ |
| Extras | ❌ oculta | ❌ oculta | ✅ |

- Os níveis só escondem; a configuração de recursos ocultos é preservada e nada impede um operador de mudar o nível.
- 🟡 Grupos internos são encontrados pelo título em português; em outro idioma o ocultamento pode falhar (code-analysis.md, achado 6).

## 5. Lacunas
- 🔴 Não há teste automatizado que garanta que nenhuma rota web aceita POST ou altera estado no futuro.
- 🟡 Ausência de TLS e de limite de tentativas na chave web.
- 🟡 O código órfão do iGate mantém uma capacidade de envio desligada, mas presente.
