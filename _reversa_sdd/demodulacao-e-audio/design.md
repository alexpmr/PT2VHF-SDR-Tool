# Demodulação e áudio, Design Técnico

## Interface

| Símbolo | Assinatura | Retorno | Observação |
|---------|-----------|---------|------------|
| `Receiver.__init__` | `(input_rate: int)` | — | `ValueError` se não for múltiplo de 240 kHz |
| `Receiver.set_offset` | `(hz: float)` | — | VFO − centro, aplicado ao NCO |
| `Receiver.set_mode` | `(mode: str, width: float \| None = None)` | — | `ValueError` para modo desconhecido |
| `Receiver.set_passband` | `(low: float, high: float)` | — | Relativo ao VFO |
| `Receiver.process` | `(iq: np.ndarray)` | `(audio_saida, audio_bruto)` | Ambos float32 a 48 kHz |
| `Receiver.signal_db` | atributo | `float` | dBFS do canal após o filtro |
| `Receiver.rec_audio_raw` / `rec_audio` | atributos | `np.ndarray` | Sem squelch / com squelch |
| `AGC.set_speed` | `(name: "Rápido" \| "Médio" \| "Lento")` | — | Default Médio |
| `Squelch.update` | `(level_db: float, nsamples: int)` | `bool` aberto | |
| `Engine.add_extra` / `remove_extra` | `(freq, mode="NFM", width=None)` / `(ex)` | `ExtraReceiver \| None` / — | Máximo 4 |
| `Engine.call` | `(fn: Callable[[Receiver], None])` | — | Executa entre blocos na thread DSP |
| `AudioOutput` | `(rate=48000, device=None, latency_s=0.15)` | — | `start`, `stop`, `write`, `underruns`, `available`, `error` |
| `Engine.audio_listeners` | lista de `Callable[[np.ndarray], None]` | — | Web, legendas |
| `Engine.audio_tap` | `Callable[[audio, raw], None] \| None` | — | Uso por ferramentas |

## Fluxo Principal
Por bloco IQ (`Receiver.process`, `dsp/receiver.py:141-182`):
1. NCO desloca o VFO para 0 Hz; `stage1` decima para 240 kHz. 🟢
2. Se `keep_if`, guarda o IF de 240 kHz para o assistente. 🟢
3. Redutor de pulsos. 🟢
4. WFM: filtro de canal a 240 kHz, nível, FM 75 kHz, de-ênfase, passa-baixa 15 kHz, decimação para 48 kHz. 🟢
5. Demais: decimação para 48 kHz, filtro de canal (257 taps), nível, demodulação; de-ênfase NFM opcional; AGC ou ganho 0,5. 🟢
6. Squelch, tom, notch, NR, EQ. 🟢
7. `rec_audio_raw` = limitador(sinal); `rec_audio` só com squelch aberto. 🟢
8. Saída = 0 se fechado ou mudo; senão limitador(sinal × volume × 2). 🟢

Na engine (`engine.py:326-436`): extras são somados com `tanh`; tone squelch pode zerar o áudio; RNNoise pode consumir o áudio (ver `reducao-de-ruido-neural`); senão `_publish_audio` entrega à placa, aos ouvintes e à gravação contínua. 🟢

## Fluxos Alternativos
- **Extra fora da faixa:** `in_span = False` e não processado. 🟢 `engine.py:393-395`
- **Comando que falha:** exceção registrada e o bloco segue. 🟢 `engine.py:333-336`
- **Underrun:** completa com zeros, `underruns += 1`, volta a encher até 150 ms. 🟢 `audio.py:99-103`
- **Excesso de áudio (clock da placa mais lento):** descarta o mais antigo acima de 500 ms. 🟢 `audio.py:77-79`

## Dependências
- NumPy e SciPy (`signal.butter`, janelas). 🟢
- sounddevice/PortAudio. 🟢
- Configuração: `mode`, `bandwidth`, `step`, `volume`, `squelch`, `agc`, `agc_speed`, `nb`, `nr`, `eq_enabled`, `eq_gains`, `wfm_deemph_us`, `audio_device`. 🟢

## Decisões de Design Identificadas

| Decisão | Evidência no código | Confiança |
|---------|---------------------|-----------|
| IF fixo de 240 kHz para todos os modos | `dsp/receiver.py:13,70` | 🟢 |
| Decoders recebem o áudio bruto, antes de AGC e squelch | `dsp/receiver.py:159,168` | 🟢 |
| Gravação independe de volume e mudo | `dsp/receiver.py:176-178` | 🟢 |
| Buffer de áudio compensa diferença de clock descartando ou preenchendo | `audio.py:30-34` | 🟢 |
| Comandos da UI como closures executadas na thread DSP | `engine.py:171,329-336` | 🟢 |

## Estado Interno
- `Receiver`: `offset_hz`, `mode`, `low`, `high`, `cw_pitch`, `volume`, `muted`, `signal_db`, filtros e demodulador reconstruídos em `_build_mode`. 🟢
- `Engine.status`: `signal_db`, `signal_sample_time`, `sq_open`, `audio_level`, `cpu`, `dropped`, `running`, `ctcss`. 🟢
- `AudioOutput`: deque de blocos, `_fill`, `_primed`, `underruns`. 🟢

## Observabilidade
- `status["cpu"]` com média exponencial (0,9/0,1). 🟢 `engine.py:455`
- `AudioOutput.underruns` e `error`. 🟢
- `log.exception` em comandos, ouvintes e DSP. 🟢

## Riscos e Lacunas
- 🟡 O volume dos extras é fixo em 0,5 e a mistura com `tanh` pode comprimir o principal.
- 🔴 Qualidade de áudio com RF real por modo não está documentada como homologada.
