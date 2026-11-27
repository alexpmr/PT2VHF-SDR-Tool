# Espectro e waterfall, Design Técnico

## Interface

| Símbolo | Assinatura | Retorno | Observação |
|---------|-----------|---------|------------|
| `compute_spectrum` | `(iq, nfft, max_frames=8, window="blackmanharris")` | `np.ndarray \| None` | dBFS com fftshift; None se o bloco < nfft |
| `Engine.wf_lines` | deque de `(spec_db, center, fs)` | — | Consumido pela UI; limpo ao retunar |
| `SpectrumWaterfall.add_line` | `(spec_db, center, fs)` | — | Desloca histórico se o centro mudou |
| `SpectrumWaterfall.set_vfo` | `(vfo, low, high)` | — | Desenha a banda passante |
| `set_levels` / `auto_levels` | `(min_db, max_db)` / `()` | — / `(min, max)` | |
| `set_colormap` | `(name)` | — | Chave de `COLORMAPS` |
| `set_markers` / `set_extras` / `set_bands` | listas | — | Sobreposições |
| `reset_zoom` / `zoom_to_vfo` / `center_on_vfo` / `clear_peak` | — | — | |
| Sinal `tuneRequested(float)` | Hz | — | Clique ou arraste da banda passante |
| Sinal `centerTuneRequested(float)` | Hz | — | Duplo clique na cascata |
| Sinal `passbandChanged(float, float)` | low, high relativos | — | Alças |
| Sinal `panRequested(float)` | novo centro | — | Pan fora da faixa |

## Fluxo Principal
1. A cada bloco, a engine acumula tempo; vencido `1/wf_speed`, calcula `compute_spectrum(blk, fft_size, 6)` e acrescenta a `wf_lines`. 🟢 `engine.py:349-356`
2. No tick de 33 ms, a UI tira linhas de `wf_lines` e chama `add_line`. 🟢 `ui/main_window.py:_tick`
3. `add_line` reduz colunas, desloca ou recria o buffer, rola a imagem, atualiza a média e o pico. 🟢 `ui/waterfall.py:219-272`
4. Clique → `_pick_frequency` → `tuneRequested` → `MainWindow.tune`. 🟢

## Fluxos Alternativos
- **Taxa ou tamanho mudou:** buffer recriado e zoom resetado. 🟢
- **Centro saltou mais que a largura:** histórico apagado. 🟢
- **Arraste da banda passante para fora:** a banda volta ao VFO atual. 🟢 `ui/waterfall.py:355-358`
- **Pan com fonte fixa ou `hold_center`:** ignorado. 🟢 `ui/main_window.py:1703`
- **Pan com frequência fora do hardware:** mensagem de `check_freq` na barra de status por 8 s. 🟢

## Dependências
- pyqtgraph (`ImageItem`, `LinearRegionItem`, `AxisItem`). 🟢
- Engine (espectro), MainWindow (sintonia e validação). 🟢
- Config: `fft_size`, `wf_min_db`, `wf_max_db`, `wf_colormap`, `wf_speed`, `spectrum_avg`, `wf_keep_vfo_centered`. 🟢

## Decisões de Design Identificadas

| Decisão | Evidência no código | Confiança |
|---------|---------------------|-----------|
| Cálculo FFT na thread DSP, desenho na UI | `engine.py:353`, `ui/waterfall.py:219` | 🟢 |
| Redução por máximo, não por média | `ui/waterfall.py:221-223` | 🟢 |
| Deslocar histórico ao mudar centro (estilo KiwiSDR) | `ui/waterfall.py:236` | 🟢 |
| Nunca sintonizar fora do IQ adquirido (v0.13.2/0.13.3) | `ui/waterfall.py:287-305`, CHANGELOG | 🟢 |

## Estado Interno
`_buf` (400 × colunas), `_buf_center`, `center`, `fs`, `_avg`, `_peak`, `peak_hold`, `min_db`, `max_db`, `step`, `vfo`, `low`, `high`, região da banda passante. 🟢

## Observabilidade
Nenhum log específico; erros de sintonia aparecem na barra de status. 🟢

## Riscos e Lacunas
- 🔴 Auto de níveis contínuo pedido no backlog; hoje é ação única.
- 🟡 Com FFT grande em UHF, o piso fixo deixa a tela preta (relato do operador).
