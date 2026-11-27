# Redução de ruído neural

## Visão Geral
Aplica RNNoise (pyrnnoise) ao áudio de fonia demodulado, numa thread própria e sem rede, com força ajustável, fallback seguro e um perfil "Sinal fraco · IA + DSP" que combina NB, NR, AGC lento e RNNoise. 🟢

## Responsabilidades
- Processar o áudio de voz em quadros de 480 amostras a 48 kHz. 🟢
- Nunca bloquear a thread RF nem silenciar o áudio por falha. 🟢
- Misturar o sinal tratado com o original pela força. 🟢
- Oferecer um perfil reversível para sinais fracos. 🟢

## Regras de Negócio
- Só em modos de voz: NFM, AM, USB, LSB e DSB; WFM, CW e RAW passam sem RNNoise. 🟢 `neural_audio.py:1-6,20`
- Nunca aplicado ao IQ nem aos decodificadores (que recebem o áudio bruto antes). 🟢 `neural_audio.py:4-5`
- Fila de 8 blocos; cheia descarta o mais antigo e conta `dropped`. 🟢 `neural_audio.py:36,56-72`
- Saída = força × tratado + (1 − força) × original, limitada a ±1; força entre 0 e 1 (padrão 0,8). 🟢 `neural_audio.py:38,104-106`
- Backend indisponível ou falha: o áudio original segue, um evento `neural_error` é emitido e o backend é desligado para o resto da sessão do worker. 🟢 `neural_audio.py:109-140`
- Backend que devolve número de amostras diferente é tratado como falha (preserva o relógio). 🟢 `neural_audio.py:100-103`
- Se o worker recusa o bloco, a engine publica o áudio direto. 🟢 `engine.py:419-421`
- Perfil "Sinal fraco": liga NB e NR (força ≥ 24), AGC lento e, se o backend existe e o modo é de voz, RNNoise; ao desligar restaura todos os controles anteriores. 🟢 `ui/main_window.py:1951-1981`
- Config: `neural_audio`, `neural_strength`. 🟢
- 🔴 Qualidade, CPU e latência com RF real não homologadas.

## Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-01 | Ligar e desligar RNNoise | Should | Worker criado e parado sem travar a DSP |
| RF-02 | Ajustar força | Should | Mistura conforme a fórmula |
| RF-03 | Fallback sem silêncio | Must | Backend com exceção mantém o áudio |
| RF-04 | Só em modos de voz | Must | WFM passa intacto |
| RF-05 | Perfil Sinal fraco reversível | Should | Restaura os controles ao desligar |

## Requisitos Não Funcionais

| Tipo | Requisito inferido | Evidência no código | Confiança |
|------|--------------------|---------------------|-----------|
| Responsividade | Inferência em thread `rnnoise-audio`, fila de 8 | `neural_audio.py:36-42` | 🟢 |
| Disponibilidade | Falha não silencia | `neural_audio.py:96-98,128-133` | 🟢 |
| Privacidade | Sem rede | `neural_audio.py:1` | 🟢 |

## Critérios de Aceitação

```gherkin
Dado RNNoise ligado em NFM com força 0,8
Quando chega áudio de voz com ruído
Então a saída é 0,8 × tratado + 0,2 × original

Dado um backend que levanta exceção
Quando o bloco é processado
Então o áudio original é tocado e surge o aviso "Falha na redução neural"

Dado o modo WFM
Quando RNNoise está ligado
Então a música passa sem tratamento

Dado o perfil Sinal fraco ligado e depois desligado
Quando o operador desliga
Então NB, NR, AGC e RNNoise voltam aos valores anteriores
```

## Prioridade (MoSCoW)

| Requisito | MoSCoW | Justificativa |
|-----------|--------|---------------|
| Fallback seguro e modos de voz | Must | Não pode degradar a escuta |
| RNNoise, força, perfil | Should | Melhoria opcional |

## Rastreabilidade de Código

| Arquivo | Função / Classe | Cobertura |
|---------|-----------------|-----------|
| `pt2vhf/neural_audio.py` | `NeuralAudioWorker`, `backend_available`, `FRAME`, `VOICE_MODES` | 🟢 |
| `pt2vhf/engine.py` | `set_neural_audio`, `process_block` | 🟢 |
| `pt2vhf/ui/main_window.py` | `_set_neural_audio`, `_weak_signal_toggled` | 🟢 |
