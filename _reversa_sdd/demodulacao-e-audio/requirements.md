# Demodulação e áudio

## Visão Geral
Converte o IQ da fonte em áudio de 48 kHz para o modo escolhido (NFM, WFM, AM, USB, LSB, CW, DSB, RAW), com squelch, AGC, filtros de áudio, receptores extras e saída na placa de som. Também distribui o áudio para gravação, painel web, legendas e decoders. 🟢

## Responsabilidades
- Deslocar o canal (NCO), decimar até 240 kHz e depois 48 kHz, filtrar e demodular. 🟢
- Medir o nível do canal em dBFS e aplicar o squelch. 🟢
- Aplicar redutor de pulsos, AGC, tom (passa-baixa), notch, redução espectral, equalizador e limitador. 🟢
- Somar até 4 receptores extras ao áudio principal. 🟢
- Tocar o áudio com buffer de latência controlada. 🟢
- Entregar áudio bruto aos decoders e áudio tratado aos ouvintes. 🟢

## Regras de Negócio
- Taxa de entrada deve ser múltiplo de 240 kHz; senão `ValueError`. 🟢 `dsp/receiver.py:55`
- Tabela de modos (low, high, passo, larguras): NFM ±6 kHz, passo 12,5 kHz; WFM ±90 kHz, passo 100 kHz; AM ±4,5 kHz, passo 5 kHz; USB +300..+2800 Hz; LSB −2800..−300 Hz; CW ±250 Hz, passo 10 Hz; DSB ±3 kHz; RAW ±12 kHz. 🟢 `dsp/receiver.py:29-38`
- WFM demodula a 240 kHz com desvio 75 kHz, de-ênfase 75 µs (ou 50 µs), passa-baixa 15 kHz e decimação para 48 kHz. 🟢 `dsp/receiver.py:106-112`
- NFM usa desvio 5 kHz se a largura > 9 kHz, senão 2,5 kHz; de-ênfase NFM opcional (750 µs). 🟢 `dsp/receiver.py:117,135`
- CW usa BFO no pitch de 700 Hz. 🟢 `dsp/receiver.py:60,121`
- AGC só em AM/USB/LSB/CW/DSB/RAW; NFM e WFM usam ganho fixo 0,5. 🟢 `dsp/receiver.py:127,171-174`
- AGC: presets Rápido (decaimento 0,05 s, hang 0,05 s), Médio (0,3/0,2) e Lento (1,0/0,5); alvo 0,3; ganho máximo 80 dB. 🟢 `dsp/demod.py:55-80`
- Squelch: −150 dBFS = sempre aberto; histerese 3 dB; cauda 0,25 s. 🟢 `dsp/demod.py:143-167`
- Com squelch fechado ou mudo, o áudio de saída é zerado, mas a gravação recebe o áudio sem squelch para a pré-gravação. 🟢 `dsp/receiver.py:175-181`
- Volume aplicado como `volume × 2` antes do limitador suave (limiar 0,9). 🟢 `dsp/receiver.py:181`, `audiofx.py:156`
- Equalizador de 8 bandas (100 Hz a 12 kHz) com presets Plano, Voz (SSB/FM), Voz clara, Graves, Música (WFM) e Telefonia. 🟢 `dsp/audiofx.py:9-19`
- Redução de ruído espectral: STFT de 512 com hop de 256, sobre-subtração 1,5, latência de 1 quadro. 🟢 `dsp/audiofx.py:104-155`
- Máximo de 4 receptores extras; só soam se estiverem dentro de 0,9·fs/2 do centro; mistura com `tanh`. 🟢 `engine.py:272-277,388-399`
- Saída de áudio: prime de 150 ms, teto de 500 ms (descarta o mais antigo); underrun zera o restante e volta a encher. 🟢 `audio.py:30-103`
- Sem placa de som, a recepção continua; `available = False` e `error` guarda o motivo. 🟢 `audio.py:50-61`

## Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-01 | Demodular NFM, WFM, AM, USB, LSB, CW, DSB e RAW | Must | Sinal sintético de cada modo produz o tom esperado |
| RF-02 | Ajustar largura por preset ou arrastando a banda passante | Must | `set_mode(mode, width)` e `set_passband(low, high)` mudam o filtro |
| RF-03 | Squelch por nível com histerese e cauda | Must | Abre no limiar e fecha 0,25 s abaixo de limiar − 3 dB |
| RF-04 | AGC com três velocidades | Must | Sinal de nível variável sai próximo de 0,3 de pico |
| RF-05 | Redutor de pulsos (NB) e redução de ruído (NR) liga/desliga | Should | Ruído impulsivo e branco reduzidos em teste sintético |
| RF-06 | Equalizador de 8 bandas com presets | Should | Ganho por banda aplicado |
| RF-07 | Notch e passa-baixa de tom | Could | Tom interferente atenuado |
| RF-08 | Até 4 receptores extras na mesma faixa | Should | O 5º `add_extra` devolve None |
| RF-09 | Escolher o dispositivo de saída | Should | `list_output_devices()` e `audio_device` |
| RF-10 | Mudo e volume | Must | Mudo zera a saída sem afetar a gravação |
| RF-11 | De-ênfase WFM 75 ou 50 µs | Should | `wfm_deemph_us` muda `wfm_deemph_tau` |

## Requisitos Não Funcionais

| Tipo | Requisito inferido | Evidência no código | Confiança |
|------|--------------------|---------------------|-----------|
| Performance | Latência de áudio de 150 ms, teto de 500 ms | `audio.py:36-41` | 🟢 |
| Performance | CPU medida como fração do tempo real do bloco | `engine.py:455` | 🟢 |
| Disponibilidade | Exceção na DSP é registrada e o loop continua | `engine.py:451-454` | 🟢 |
| Disponibilidade | Falha de ouvinte de áudio não derruba a cadeia | `engine.py:113-117` | 🟢 |

## Critérios de Aceitação

```gherkin
Dado o simulador com uma portadora NFM modulada por 1 kHz
Quando o operador escolhe NFM com largura 12,5 kHz
Então o áudio de saída contém 1 kHz e o nível em dBFS é atualizado

Dado o squelch em -80 dBFS e um sinal a -70 dBFS
Quando o sinal cai para -85 dBFS
Então o squelch fecha depois de 0,25 s e a saída fica em silêncio

Dado 4 receptores extras ativos
Quando o operador tenta adicionar um quinto
Então nenhum receptor é criado

Dado que não existe placa de som
Quando a recepção começa
Então a engine segue processando e o motivo aparece em AudioOutput.error

Dado uma taxa de 1 MS/s
Quando o Receiver é criado
Então ele levanta ValueError
```

## Prioridade (MoSCoW)

| Requisito | MoSCoW | Justificativa |
|-----------|--------|---------------|
| Demodulação dos modos e squelch | Must | Caminho crítico de toda escuta |
| AGC, volume e mudo | Must | Usados em todo modo AM/SSB |
| Saída de áudio | Must | Sem ela não há escuta local |
| NB, NR, EQ | Should | Melhoram, com alternativa (RNNoise) |
| Receptores extras | Should | Uso avançado |
| Notch e tom | Could | Casos específicos |

## Rastreabilidade de Código

| Arquivo | Função / Classe | Cobertura |
|---------|-----------------|-----------|
| `pt2vhf/dsp/receiver.py` | `Receiver`, `MODES`, `ModeInfo`, `passband_for`, `SAMPLE_RATES` | 🟢 |
| `pt2vhf/dsp/demod.py` | `FMDemod`, `AMDemod`, `SSBDemod`, `AGC`, `NoiseBlanker`, `Squelch`, `power_db` | 🟢 |
| `pt2vhf/dsp/filters.py` | `NCO`, `FIRFilter`, `Decimator`, `SOSFilter`, `IIRFilter`, `bandpass_complex_taps`, `deemphasis`, `DCBlocker` | 🟢 |
| `pt2vhf/dsp/audiofx.py` | `Equalizer`, `Notch`, `ToneFilters`, `NoiseReduction`, `soft_limiter` | 🟢 |
| `pt2vhf/audio.py` | `AudioOutput`, `list_output_devices` | 🟢 |
| `pt2vhf/engine.py` | `Engine.process_block`, `ExtraReceiver`, `add_extra`, `_publish_audio` | 🟢 |
