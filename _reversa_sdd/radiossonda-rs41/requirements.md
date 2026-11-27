# Radiossonda RS41

## Visão Geral
Decodifica radiossondas Vaisala RS41 a partir do **mesmo IQ** do SDR em uso: canaliza a frequência da sonda para IQ int16 de 48 kS/s e alimenta os binários externos `fsk_demod` e `rs41mod` (projeto radiosonde_auto_rx). Mostra quadros, posição, altitude e diagnóstico. **Estado: P0 aberto, sem prova com RF real.** 🔴

## Responsabilidades
- Validar fonte, frequência e binários antes de iniciar. 🟢
- Deslocar e decimar o canal da sonda para 48 kS/s sem travar a DSP. 🟢
- Rodar `fsk_demod | rs41mod` como processos sem shell e ler o JSON. 🟢
- Transformar quadros em `Track` e publicá-los na UI. 🟢
- Expor diagnóstico (blocos, bytes, quadros, erros, processos vivos). 🟢
- Capturar IQ de 48 kS/s para diagnóstico reproduzível. 🟢

## Regras de Negócio
- Frequência entre 400 e 406 MHz; senão `ValueError`. 🟢 `sonde_rx.py:42-45`
- IQ de entrada ≥ 96 kS/s; a sonda deve estar a mais de 30 kHz da borda da banda capturada. 🟢 `sonde_rx.py:62-63,80-82`
- Exige receptor ligado e fonte física ou arquivo IQ; o simulador é recusado. 🟢 `ui/main_window.py:1472-1480`
- A UI sintoniza a frequência da sonda antes de iniciar. 🟢 `ui/main_window.py:1481`
- Canal centrado em 0 Hz (banda base), porque o `fsk_demod` atual usa máscara de −5 a +5 kHz; a docstring do módulo ainda fala em FI +12 kHz. 🟢 `sonde_rx.py:26,104-106`, commit fa10118. 🟡 Docstring desatualizada.
- Taxas múltiplas de 48 kS/s usam IIR de 10ª ordem (19 kHz) e seleção com fase contínua; outras usam `resample_poly` com histórico. 🟢 `sonde_rx.py:66-103`
- Saída int16 LE intercalada com escala 30 000. 🟢 `sonde_rx.py:107-109`
- Comandos: `fsk_demod --cs16 -b -5000 -u 5000 -s --mask 5000 --nsym=300 -p 5 --stats=5 2 48000 4800 - -` e `rs41mod --ptu2 --json --jsnsubfrm1 --softin -i --jsn_cfq <Hz>`. 🟢 `sonde_rx.py:46-51`
- Binários só do caminho informado ou do PATH; nunca baixados automaticamente. 🟢 `sonde_rx.py:29-39`
- A thread DSP só copia o bloco para uma fila de 12; fila cheia conta `dropped`. Mudança de taxa durante a decodificação conta como perda e pede reinício. 🟢 `sonde_rx.py:178-192`
- Linhas que não começam com `{` são ignoradas; JSON inválido conta `invalid_json`; quadro sem posição conta `unpositioned_frames` e vai para `sonde_frame`. 🟢 `sonde_rx.py:225-251`
- stderr com "error", "usage" ou "invalid" vira status; linhas com SNR/stats viram `last_demod_stats`. 🟢 `sonde_rx.py:257-272`
- Captura: 1 a 60 s (padrão 20 s) de IQ 48 kS/s; só uma por vez. 🟢 `sonde_rx.py:291-317`
- Parar: termina os processos e mata após 1 s. 🟢 `sonde_rx.py:319-335`
- IQ recebido ou sinal no waterfall não provam telemetria; só serial, quadro, posição e altitude no mapa com RF real. 🔴 CLAUDE.md

## Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-01 | Iniciar RS41 na frequência escolhida | Must | Processos vivos e status "aguardando quadros válidos" |
| RF-02 | Recusar condições inválidas | Must | Mensagens para receptor desligado, simulador, faixa e binário ausente |
| RF-03 | Publicar posição e altitude | Must | Evento `sonde_rx` com `Track` |
| RF-04 | Mostrar quadros sem posição | Should | Evento `sonde_frame` |
| RF-05 | Diagnóstico | Must | `diagnostics()` com contadores |
| RF-06 | Captura IQ | Should | Arquivo int16 LE 48 kS/s |
| RF-07 | Homologação com RF real | Must | 🔴 pendente |

## Requisitos Não Funcionais

| Tipo | Requisito inferido | Evidência no código | Confiança |
|------|--------------------|---------------------|-----------|
| Responsividade | DSP só enfileira; conversão e escrita em thread própria | `sonde_rx.py:178-222` | 🟢 |
| Segurança | Subprocessos sem shell, sem janela no Windows | `sonde_rx.py:149-160` | 🟢 |
| Segurança | Sem download automático de binários | `sonde_rx.py:29-39` | 🟢 |
| Disponibilidade | Encerramento com timeout de 1 s e kill | `sonde_rx.py:330-335` | 🟢 |

## Critérios de Aceitação

```gherkin
Dado o receptor desligado
Quando o operador inicia RS41
Então aparece "Ligue primeiro o receptor SDR. O waterfall isolado não decodifica."

Dado o simulador como fonte
Quando o operador inicia RS41
Então aparece "Selecione um receptor físico ou um arquivo IQ gravado."

Dado fsk_demod ausente do PATH
Quando o operador inicia RS41
Então aparece a orientação para instalar os demoduladores do radiosonde_auto_rx

Dado 405,1 MHz
Quando build_decoder_commands é chamado com 410 MHz
Então levanta "A recepção RS41 configurada suporta a faixa 400–406 MHz"

Dado uma RS41 real em voo dentro do alcance
Quando a decodificação roda por 5 minutos
Então o serial, o número do quadro, a posição e a altitude aparecem no mapa
# 🔴 cenário de homologação, nunca demonstrado
```

## Prioridade (MoSCoW)

| Requisito | MoSCoW | Justificativa |
|-----------|--------|---------------|
| Pipeline e validações | Must | P0 do BACKLOG |
| Diagnóstico e captura | Must | Necessários para fechar o P0 |
| Homologação RF | Must | Critério de aceite |

## Rastreabilidade de Código

| Arquivo | Função / Classe | Cobertura |
|---------|-----------------|-----------|
| `pt2vhf/sonde_rx.py` | `find_binary`, `build_decoder_commands`, `ChannelIQ`, `RS41Receiver`, `OUTPUT_RATE`, `SIGNAL_OFFSET_HZ` | 🟢 |
| `pt2vhf/traffic.py` | `parse_radiosondes` | 🟢 |
| `pt2vhf/ui/sonde_decoder_panel.py` | `SondeDecoderPanel` | 🟢 |
| `pt2vhf/ui/main_window.py` | `_start_sonde`, `_stop_sonde`, eventos `sonde_*` | 🟢 |
| `pt2vhf/engine.py` | `iq_listeners` | 🟢 |
