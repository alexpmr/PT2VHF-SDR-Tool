# Tons DTMF e CTCSS

## Visão Geral
Detecta teclas DTMF e o subtom CTCSS no áudio NFM e usa o CTCSS como tone squelch, para ouvir só a estação com o tom configurado. 🟢

## Responsabilidades
- Detectar dígitos DTMF (16 teclas) com Goertzel. 🟢
- Detectar o subtom CTCSS entre 51 tons padrão em janelas de 1 s. 🟢
- Silenciar o áudio quando o tone squelch está ligado e o tom não confere. 🟢
- Expor o CTCSS medido para memórias e para o display. 🟢

## Regras de Negócio
- Só em NFM; cada detector liga por `decoders.dtmf` e `decoders.ctcss`. Ambos recebem o áudio bruto. 🟢 `engine.py:400-407`
- DTMF: 8 kHz, quadro de 205 amostras (~25,6 ms); grupo baixo 697/770/852/941 Hz e alto 1209/1336/1477/1633 Hz; teclas `123A 456B 789C *0#D`. 🟢 `decoders/tones.py:16-48`
- DTMF aceita o quadro se os dois tons somam > 60% da energia, o 2º maior de cada grupo < 15% do maior e o twist está entre −8 e +8 dB; o dígito é emitido uma vez após 2 quadros iguais seguidos. 🟢 `decoders/tones.py:58-78`
- CTCSS: 48 kHz → 6 kHz → 1 kHz; janela de 1 s com Hann; tom aceito se o pico > 15 dB sobre a mediana dos outros tons (excluindo vizinhos) e > 2% da energia. 🟢 `decoders/tones.py:81-115`
- Lista de 51 tons de 67,0 a 254,1 Hz. 🟢 `decoders/tones.py:8-14`
- Tone squelch: se ligado e o CTCSS medido estiver ausente ou diferir mais de 1 Hz, o áudio é zerado e a gravação considera o squelch fechado. 🟢 `engine.py:407-412,423-425`
- Tone squelch dispensa o squelch por nível para o VOX. 🟢 `ui/main_window.py:1129`
- Salvar a memória atual grava o CTCSS medido. 🟢 `ui/main_window.py:1221`

## Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-01 | Detectar DTMF | Should | Sequência sintética "123#" detectada uma vez cada |
| RF-02 | Detectar CTCSS | Should | 88,5 Hz sintético reconhecido |
| RF-03 | Tone squelch | Should | Áudio só com o tom configurado |
| RF-04 | Mostrar o tom medido | Should | `status["ctcss"]` |

## Requisitos Não Funcionais

| Tipo | Requisito inferido | Evidência no código | Confiança |
|------|--------------------|---------------------|-----------|
| Latência | CTCSS com janela de 1 s | `decoders/tones.py:84-91` | 🟢 |
| Performance | Goertzel em vez de FFT | `decoders/tones.py:24` | 🟢 |

## Critérios de Aceitação

```gherkin
Dado NFM com DTMF ligado
Quando chegam os tons de "5" por 100 ms
Então o dígito 5 é emitido uma vez

Dado tone squelch em 88,5 Hz
Quando a estação transmite com 100,0 Hz
Então o áudio fica em silêncio

Dado tone squelch em 88,5 Hz
Quando a estação transmite com 88,5 Hz
Então o áudio passa

Dado ruído sem tom
Quando o CTCSS é medido
Então status["ctcss"] fica None
```

## Prioridade (MoSCoW)

| Requisito | MoSCoW | Justificativa |
|-----------|--------|---------------|
| CTCSS e tone squelch | Should | Uso em repetidoras |
| DTMF | Should | Diagnóstico |

## Rastreabilidade de Código

| Arquivo | Função / Classe | Cobertura |
|---------|-----------------|-----------|
| `pt2vhf/decoders/tones.py` | `goertzel_power`, `DTMFDecoder`, `CTCSSDetector`, `CTCSS_TONES`, `DTMF_*` | 🟢 |
| `pt2vhf/engine.py` | `dtmf`, `ctcss`, `tone_squelch`, `process_block` | 🟢 |
