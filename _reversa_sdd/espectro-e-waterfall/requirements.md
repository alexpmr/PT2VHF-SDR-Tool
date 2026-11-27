# Espectro e waterfall

## Visão Geral
Mostra o espectro médio e a cascata (waterfall) do IQ adquirido, com marcação do VFO e da banda passante, e permite sintonizar clicando, arrastando e usando o zoom. 🟢

## Responsabilidades
- Calcular o espectro por FFT a partir dos blocos IQ, na thread DSP. 🟢
- Desenhar a curva média, o pico (peak hold) e a cascata com paletas. 🟢
- Converter um ponto da tela em frequência, só dentro do IQ adquirido. 🟢
- Sintonizar por clique, duplo clique (sintoniza e centraliza), arraste da banda passante e arraste da vista (pan). 🟢
- Ajustar níveis (piso/teto) manual ou automaticamente. 🟢
- Mostrar marcadores (memórias, acertos), receptores extras e faixas do plano de bandas. 🟢

## Regras de Negócio
- Uma linha de espectro a cada `1/wf_speed` s (padrão 20 linhas/s), com até 6 quadros FFT médios por bloco, janela Blackman-Harris. 🟢 `engine.py:349-356`, `dsp/receiver.py:183-196`
- Espectro em dBFS com `fftshift` (−fs/2..+fs/2). 🟢 `dsp/receiver.py:185`
- Tamanho da FFT padrão 4096 (`fft_size`). 🟢 `config.py:58`
- A cascata guarda 400 linhas; acima de 2048 colunas reduz por máximo para preservar sinais estreitos. 🟢 `ui/waterfall.py:52,217-223`
- Ao mudar o centro sem mudar a taxa, o histórico é deslocado em vez de apagado. 🟢 `ui/waterfall.py:235-252`
- Curva média com alfa 0,5 (`spectrum_avg`). 🟢 `ui/waterfall.py:54,268`
- Níveis padrão −110 a −40 dB; teto mínimo = piso + 5 dB. 🟢 `config.py:59-60`, `ui/waterfall.py:133-135`
- Níveis automáticos: piso = percentil 20 − 8 dB; teto = max(percentil 99,8 + 8, piso + 30). Ação única por botão ou Ctrl+L. 🟢 `ui/waterfall.py:143-149`, `ui/main_window.py:684`
- Clique só vale dentro de [centro − fs/2, centro + fs/2]; a frequência é arredondada ao passo e recusada se o arredondamento cair fora. 🟢 `ui/waterfall.py:287-305`
- Clique simples no espectro, dentro da banda passante, não sintoniza (reservado às alças). 🟢 `ui/waterfall.py:324-328`
- Duplo clique no espectro = zoom total; duplo clique na cascata = sintoniza e centraliza, só se a sintonia for aceita. 🟢 `ui/waterfall.py:315-322`, `ui/main_window.py:1635-1642`
- Arrastar a banda passante inteira sintoniza; mudar a largura emite `passbandChanged`. 🟢 `ui/waterfall.py:345-361`
- Pan para fora da faixa recebida pede novo centro, se o deslocamento > 10% de fs e a vista < 1,05·fs, e se a fonte for sintonizável e o centro não estiver preso. 🟢 `ui/waterfall.py:334-343`, `ui/main_window.py:1700-1712`
- Roda do mouse com Ctrl sintoniza por passo; sem Ctrl, zoom. 🟢 `ui/waterfall.py:364`
- Paletas: Kiwi, SDR#, Fósforo, Âmbar, Cinza, Inferno. 🟢 `ui/waterfall.py:19-30`
- Pedido no backlog, **não implementado**: Auto de níveis como liga/desliga contínuo; com piso fixo, acima de 800 MHz com FFT 32768 a tela fica preta. 🔴 memória do projeto

## Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-01 | Espectro e cascata atualizados em tempo real | Must | Linha nova a cada 1/`wf_speed` s |
| RF-02 | Clique sintoniza no IQ adquirido | Must | Clique fora da faixa não muda o VFO |
| RF-03 | Duplo clique sintoniza e centraliza | Must | Sintonia recusada não move a vista |
| RF-04 | Arrastar e redimensionar a banda passante | Must | Arrastar move o VFO; alças mudam a largura |
| RF-05 | Pan que retunea o SDR | Should | Vista fora da faixa gera novo centro |
| RF-06 | Níveis manual e automático | Must | Ctrl+L aplica os percentis |
| RF-07 | Peak hold e limpar pico | Should | Curva de pico acumula o máximo |
| RF-08 | Paletas de cores | Should | 6 paletas selecionáveis |
| RF-09 | Marcadores, extras e faixas de banda | Should | Aparecem nas frequências certas |
| RF-10 | Manter o VFO centralizado (opcional) | Could | `wf_keep_vfo_centered` |
| RF-11 | Auto de níveis contínuo | Could | Backlog, não implementado 🔴 |

## Requisitos Não Funcionais

| Tipo | Requisito inferido | Evidência no código | Confiança |
|------|--------------------|---------------------|-----------|
| Performance | FFT na thread DSP, limitada a 6 quadros por bloco | `engine.py:353` | 🟢 |
| Performance | Cascata reduzida a 2048 colunas por máximo | `ui/waterfall.py:217-223` | 🟢 |
| Responsividade | Widgets atualizados só na thread principal pelo tick | `ui/main_window.py:_tick` | 🟢 |

## Critérios de Aceitação

```gherkin
Dado o receptor centrado em 145,800 MHz a 2,4 MS/s
Quando o operador clica na cascata em 145,512 MHz com passo de 12,5 kHz
Então o VFO vai para 145,5125 MHz

Dado o mesmo receptor
Quando o operador clica em 147,500 MHz, fora do IQ adquirido
Então nada é sintonizado

Dado um duplo clique na cascata numa frequência que o SDR recusa
Quando a sintonia falha
Então a vista não é centralizada

Dado um espectro com ruído de -100 dB e um sinal de -50 dB
Quando o operador pressiona Ctrl+L
Então o piso fica perto de -108 dB e o teto acima de -42 dB
```

## Prioridade (MoSCoW)

| Requisito | MoSCoW | Justificativa |
|-----------|--------|---------------|
| Espectro, cascata e clique para sintonizar | Must | Principal forma de navegar |
| Arraste da banda passante e níveis | Must | Uso constante |
| Pan, peak hold, paletas, marcadores | Should | Conforto |
| VFO centralizado, Auto contínuo | Could | Opcional / backlog |

## Rastreabilidade de Código

| Arquivo | Função / Classe | Cobertura |
|---------|-----------------|-----------|
| `pt2vhf/dsp/receiver.py` | `compute_spectrum`, `_window` | 🟢 |
| `pt2vhf/engine.py` | `process_block` (trecho de espectro), `wf_lines`, `spectrum`, `fft_size`, `wf_speed` | 🟢 |
| `pt2vhf/ui/waterfall.py` | `SpectrumWaterfall`, `COLORMAPS`, `make_lut`, `MHzAxis` | 🟢 |
| `pt2vhf/ui/main_window.py` | `select_transmission_centered`, `_pan_to`, `_auto_levels`, `_center_waterfall` | 🟢 |
