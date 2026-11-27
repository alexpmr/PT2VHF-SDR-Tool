# CAT · Hamlib rigctld, Design Técnico

## Interface

| Símbolo | Assinatura | Retorno | Observação |
|---------|-----------|---------|------------|
| `RigCtlClient` | `(host="127.0.0.1", port=4532, timeout=1.5)` | — | `ValueError` em host vazio ou porta inválida |
| `RigCtlClient.read` | `()` | `(hz: float, modo_sdr: str)` | Comandos `f` e `m` |
| `RigCtlClient.write` | `(hz, sdr_mode)` | `None` | Comandos `F <hz>` e `M <modo> 0` |
| `RigCtlPanel` | `(cfg, current_sdr_tuning, parent=None)` | — | Sinal `readReceived(float, str)`; `stop()` |
| `MainWindow._cat_received` | `(freq, mode)` | — | Valida e chama `set_mode`/`tune` |

Protocolo em [contracts.md](contracts.md).

## Fluxo Principal (ler)
1. Clique ou temporizador chama `_run("get")`; cria um `RigCtlClient` e submete `read` ao pool de 1 worker. 🟢
2. O temporizador de 300 ms (thread da UI) verifica o `Future`; ao terminar, emite `readReceived`. 🟢
3. `_cat_received` confere faixa e suporte da fonte e sintoniza. 🟢

## Fluxo Principal (enviar)
1. `_run("set")` obtém `(engine.vfo, mode)` e submete `write`. 🟢
2. Sucesso mostra "Frequência e modo enviados ao rádio. PTT não foi acionado." 🟢

## Fluxos Alternativos
- **Erro de rede, Hamlib ou valor:** `OSError`, `ValueError`, `RuntimeError` ou `UnicodeError` vão para o status com prefixo "CAT: ". 🟢
- **Operação em andamento:** novo clique é ignorado. 🟢
- **Fechar:** `stop()` para o temporizador e encerra o pool sem esperar. 🟢

## Dependências
- Hamlib `rigctld` externo (integrations.md). 🟢
- `MainWindow.tune`, `set_mode`, `_freq_supported`. 🟢

## Decisões de design
- Conexão por comando, em vez de sessão persistente: simples e sem estado. 🟢
- Sem PTT por política do produto (CLAUDE.md: aplicativo receptor). 🟢

## Lacunas
- 🔴 Nunca demonstrado com transceptor real.
- 🟡 Faixa aceita na leitura (24 kHz–1766 MHz) é a dívida D3 (`architecture.md`).
