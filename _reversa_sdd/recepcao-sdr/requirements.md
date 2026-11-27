# Recepção SDR

## Visão Geral
Aquisição contínua de amostras IQ de um receptor SDR (RTL-SDR local, rtl_tcp, SoapySDR, arquivo WAV IQ ou simulador) e entrega em blocos à engine DSP, com sintonia segura do centro e recuperação automática do dongle. 🟢

## Responsabilidades
- Abrir, configurar e fechar a fonte IQ escolhida pelo operador. 🟢
- Entregar blocos `complex64` numa fila limitada, sem bloquear a thread DSP. 🟢
- Aplicar frequência central, ganho, PPM, bias-T e amostragem direta. 🟢
- Recusar frequências fora do alcance do hardware, com mensagem explicativa. 🟢
- Detectar travamento ou ausência de amostras e reconectar o RTL-SDR. 🟢
- Instalar o driver WinUSB no Windows quando necessário. 🟢

## Regras de Negócio
- Fila de 32 blocos; cheia, descarta o mais antigo e incrementa `dropped`. 🟢 `sources/base.py:60`
- Bloco = max(16384, ⌊fs/20/16384⌋·16384), cerca de 20 blocos/s. 🟢 `sources/base.py:39`
- Taxas aceitas: 240 k, 960 k, 1,2 M, 1,44 M, 1,92 M, 2,4 M e 2,88 MS/s (múltiplos de 240 kHz). 🟢 `dsp/receiver.py:17`
- A UI nunca chama a librtlsdr diretamente; tudo passa por fila e thread de controle. 🟢 `sources/rtlsdr_source.py:1`
- Watchdog: sem blocos por `STALL_S` = 2 s ou comando sem retorno por `CMD_TIMEOUT_S` = 3 s → reconecta, até `MAX_RECOVER` = 3 vezes; depois `failed`. 🟢 `rtlsdr_source.py:171-173,478-503`
- Faixa por sintonizador: E4000 52–2200 MHz; FC0012/13 22–1100 MHz; FC2580 146–924 MHz; R820T/R828D 24–1766 MHz; RTL-SDR Blog V4 com biblioteca Blog 0,5–1766 MHz (HF pelo upconverter interno); amostragem direta 0,5–28,8 MHz. 🟢 `rtlsdr_source.py:149-162`
- Frequência salva fora do alcance abre em 145,5 MHz. 🟢 `rtlsdr_source.py:265`
- No Windows, a biblioteca RTL-SDR Blog é tentada primeiro, com stubs para funções ausentes, e cai para a padrão. 🟢 `rtlsdr_source.py:31-130`
- O centro é deslocado para VFO + fs/8 quando fs ≥ 900 kHz, para afastar o VFO do pico de DC. 🟢 `engine.py:219`
- A média do bloco é subtraída (remoção de DC) antes de qualquer processamento. 🟢 `engine.py:338`
- WinUSB só na interface 0 do dispositivo composto, via `wdi-simple` com um único UAC. 🟢 `sources/rtl_driver.py:93-125`
- `set_center_freq` fora da faixa: RTL-SDR devolve `False`; rtl_tcp e SoapySDR levantam `SourceError`. 🟢 `network_sources.py:86,175`. 🟡 A engine só trata `False`.
- Para o RTL-SDR Blog V4L do operador, HF deve ir pelo upconverter, nunca pela amostragem direta. 🟡 decisão do operador registrada em memória do projeto.

## Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-01 | Abrir RTL-SDR local por índice e listar dispositivos | Must | `list_devices()` retorna nomes; `start()` entrega blocos |
| RF-02 | Abrir rtl_tcp por host e porta | Must | Blocos chegam de um servidor rtl_tcp |
| RF-03 | Abrir SoapySDR por string de argumentos | Should | `soapy_devices()` lista e a fonte entrega blocos |
| RF-04 | Reproduzir WAV IQ com centro fixo (`tunable = False`) | Should | O canal se desloca dentro da faixa gravada sem retune |
| RF-05 | Simulador sem hardware (`--sim`) com sinais e Morse | Must | `python run_pt2vhf.py --sim` produz áudio e espectro |
| RF-06 | Ajustar ganho (manual/AGC), PPM, bias-T e amostragem direta | Must | Comando aplicado sem travar a UI |
| RF-07 | Recusar frequência fora da faixa com texto explicativo | Must | `check_freq` devolve mensagem; centro anterior mantido |
| RF-08 | Recuperar o dongle travado até 3 vezes | Must | Evento `source_msg` com tentativa n/3 e "Recepção restabelecida." |
| RF-09 | Indicar falha definitiva e pedir reconexão física | Must | `status = failed` e mensagem de desconectar e clicar Ligar |
| RF-10 | Instalar WinUSB com uma elevação | Should | Após o UAC, a interface 0 aparece com serviço WinUSB |
| RF-11 | Contar blocos perdidos | Should | `engine.status["dropped"]` aumenta quando a DSP atrasa |

## Requisitos Não Funcionais

| Tipo | Requisito inferido | Evidência no código | Confiança |
|------|--------------------|---------------------|-----------|
| Disponibilidade | Reconexão automática com 3 tentativas | `sources/rtlsdr_source.py:478-503` | 🟢 |
| Performance | Comando ao dongle com timeout de 3 s | `sources/rtlsdr_source.py:172` | 🟢 |
| Performance | Fila limitada a 32 blocos com descarte | `sources/base.py:33,58-68` | 🟢 |
| Segurança | Elevação só para trocar driver, com UAC explícito | `sources/rtl_driver.py:104-125` | 🟢 |
| Responsividade | UI nunca bloqueia em chamada ao driver | `sources/rtlsdr_source.py:1` | 🟢 |

## Critérios de Aceitação

```gherkin
Dado um RTL-SDR R820T conectado
Quando o operador sintoniza 145,500 MHz a 2,4 MS/s
Então o centro vai para 145,800 MHz e o VFO fica a -300 kHz do centro

Dado um RTL-SDR R820T conectado
Quando o operador pede 7,100 MHz sem amostragem direta
Então a sintonia é recusada com a faixa 24–1766 MHz e a dica de HF
E o centro anterior é mantido

Dado um dongle que para de entregar amostras
Quando passam 2 s sem blocos
Então o status vai para recovering e a fonte é reaberta
E após 3 falhas seguidas o status vai para failed com a mensagem de reconectar

Dado uma fonte rtl_tcp
Quando o operador pede uma frequência fora da faixa
Então a fonte levanta SourceError
```

## Prioridade (MoSCoW)

| Requisito | MoSCoW | Justificativa |
|-----------|--------|---------------|
| RTL-SDR local com watchdog | Must | Fonte principal e caminho crítico |
| Simulador | Must | Base de testes e `--sim` |
| rtl_tcp | Should | Alternativa remota |
| SoapySDR | Should | Sem testes dedicados |
| WAV IQ | Should | Reprodução e diagnóstico |
| Instalação WinUSB | Should | Só no Windows, primeira execução |

## Rastreabilidade de Código

| Arquivo | Função / Classe | Cobertura |
|---------|-----------------|-----------|
| `pt2vhf/sources/base.py` | `IQSource`, `SourceError`, `u8_to_complex` | 🟢 |
| `pt2vhf/sources/rtlsdr_source.py` | `RtlSdrSource`, `tuning_range`, `load_library`, `_DllWithStubs` | 🟢 |
| `pt2vhf/sources/network_sources.py` | `RtlTcpSource`, `SoapySource`, `soapy_devices` | 🟢 |
| `pt2vhf/sources/sim_sources.py` | `SimulatorSource`, `WavIQSource`, `morse_keying` | 🟢 |
| `pt2vhf/sources/rtl_driver.py` | `windows_needs_winusb`, `install_winusb` | 🟢 |
| `pt2vhf/engine.py` | `Engine.start`, `_retune`, `_loop` | 🟢 |
