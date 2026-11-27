# Recepção SDR, Design Técnico

## Interface

| Símbolo | Assinatura | Retorno | Observação |
|---------|-----------|---------|------------|
| `IQSource.__init__` | `(sample_rate: int, center_freq: float)` | — | Define `block_size`, fila de 32 e `dropped = 0` |
| `IQSource.start` / `stop` | `()` | — | Thread `src-<nome>`; `stop` faz join de 2 s |
| `IQSource.read` | `(timeout: float = 0.5)` | `np.ndarray \| None` | Bloco `complex64` ou None |
| `IQSource.check_freq` | `(hz: float)` | `str` | `""` se alcançável, senão explicação |
| `IQSource.set_center_freq` | `(hz: float)` | `bool \| None` | RTL: `False` fora da faixa; rede/Soapy: `SourceError` |
| `IQSource.set_gain` | `(db: float \| None)` | — | `None` = AGC do sintonizador |
| `IQSource.set_ppm` / `set_bias_tee` / `set_direct_sampling` | `(int)` / `(bool)` / `(int)` | — | Conforme `supports_*` |
| Atributos de capacidade | `tunable`, `supports_gain`, `supports_ppm`, `supports_bias_tee`, `supports_direct_sampling`, `gains_db` | — | A UI habilita controles por eles |
| `RtlSdrSource.status` | `"ok" \| "recovering" \| "failed"` | — | Ver `state-machines.md` §1 |
| `RtlSdrSource.pop_messages` | `()` | `list[str]` | Mensagens para o operador; a engine as publica como `source_msg` |
| `tuning_range` | `(tuner, blog_lib, direct_sampling, product)` | `(lo, hi)` Hz | Tabela por sintonizador |
| `load_library` / `set_preference` / `library_info` | `(kind)` / `(lib)` / `()` | — / — / `dict` | Seleção Blog ou padrão |
| `install_winusb` | `(pid: str)` | `(bool, str)` | `ShellExecuteEx` com `runas` |
| `Engine.start` | `(source: IQSource)` | — | Cria Receiver, timeshift e thread DSP |

## Fluxo Principal
1. A UI cria a fonte pela configuração `source` e chama `Engine.start(source)`. 🟢 `ui/main_window.py`, `engine.py:123`
2. A fonte abre o hardware e roda a thread de leitura, que chama `_push(bloco)`. 🟢 `sources/base.py:58`
3. Para o RTL-SDR, comandos são enfileirados por `_submit(nome, fn)` e executados pela thread de controle; o vigia mede `_busy_since` e `_last_block`. 🟢 `rtlsdr_source.py:437-503`
4. A engine lê com `read(timeout=0.5)`, publica mensagens da fonte e processa o bloco. 🟢 `engine.py:438-458`
5. Ao sintonizar, `Engine._retune` calcula a margem `fs/2·0,9 − largura/2`; fora dela, pede novo centro `VFO + fs/8`. 🟢 `engine.py:206-226`

## Fluxos Alternativos
- **Fonte com centro fixo (`tunable = False`) ou `hold_center`:** só o offset do canal muda, limitado a ±0,95·fs/2. 🟢 `engine.py:212-216`
- **RTL fora da faixa:** `set_center_freq` devolve `False`; a engine mantém o centro e limita o offset. 🟢 `engine.py:220-223`
- **rtl_tcp/Soapy fora da faixa:** `SourceError` propaga; 🔴 não tratado em `_retune` (dívida D2).
- **Dongle travado:** `recovering`, cancelamento da leitura antiga em thread separada, reabertura; após 3 tentativas, `failed` e fim do vigia. 🟢
- **Fonte parou:** `read` devolve None e `_running` é falso → evento `error` "A fonte de sinal parou." 🟢 `engine.py:445-447`

## Dependências
- `pyrtlsdr` e DLLs librtlsdr (Blog e padrão) embarcadas. 🟢
- `SoapySDR` (opcional, importado sob demanda). 🟡
- `ctypes`/`wintypes` para `ShellExecuteEx` e `wdi-simple.exe`. 🟢
- Engine (consumidor dos blocos). 🟢

## Decisões de Design Identificadas

| Decisão | Evidência no código | Confiança |
|---------|---------------------|-----------|
| Fila de controle com watchdog (ADR 001) | `rtlsdr_source.py:478-503` | 🟢 |
| Biblioteca Blog com stubs e fallback (ADR 002) | `rtlsdr_source.py:41-130` | 🟢 |
| WinUSB com um UAC (ADR 007) | `rtl_driver.py:104-125` | 🟢 |
| Offset fs/8 contra o pico de DC | `engine.py:219` | 🟢 |
| Fila com descarte do mais antigo | `sources/base.py:58-68` | 🟢 |

## Estado Interno
- `center_freq`, `sample_rate`, `block_size`, `dropped`, `_running`, `_q`. 🟢
- RTL: `status`, `tuner`, `product`, `direct_sampling`, `bias_tee`, `_busy_since`, `_last_block`, mensagens pendentes. 🟢
- Configuração persistida: `source`, `device_index`, `device_name`, `rtl_tcp_host`, `rtl_tcp_port`, `soapy_args`, `sample_rate`, `center_freq`, `gain`, `ppm`, `bias_tee`, `direct_sampling`, `reconnect_on_start`, `rtl_library`. 🟢 `config.py`

## Observabilidade
- Mensagens ao operador via `pop_messages` → evento `source_msg`. 🟢
- `engine.status["dropped"]` e `status["cpu"]`. 🟢
- Log `pt2vhf-sdr.log` com `log.exception` em comandos que falham. 🟢 `engine.py:336`

## Riscos e Lacunas
- 🔴 Comportamento real do watchdog com rtl_tcp e SoapySDR sob falha.
- 🟡 Limite de UI 24 kHz–1766 MHz aplicado a todas as fontes (dívida D3).
- 🟡 Contrato inconsistente de `set_center_freq` (dívida D2).
- 🔴 Sem testes para `rtl_driver.py` e SoapySDR (dívida D10).
