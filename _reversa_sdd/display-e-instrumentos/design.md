# Display e instrumentos, Design Técnico

## Interface

| Símbolo | Assinatura | Retorno | Observação |
|---------|-----------|---------|------------|
| `LCDDisplay.set_freq` | `(f: float)` | — | |
| `LCDDisplay.set_signal` | `(dbm: float \| None, s_text: str, sq_open: bool)` | — | None = sem medição |
| `LCDDisplay.set_theme` | `(name)` | — | Chave de `THEMES` |
| `LCDDisplay.set_preferred_scale` | `(percent: int)` | — | Limitado a 50–150 |
| `LCDDisplay.attach_band_keys` | `(band_bar)` | — | Posiciona as teclas no LCD |
| `LCDDisplay.meter_segments` | `(dbm, valid=True, nseg=40)` | `int` | Estático |
| Sinais do LCD | `freqChanged(float)`, `stepRequested(int)`, `modeClicked(str)`, `neighborRequested(int)`, `autoTuneToggled()` | — | |
| `BandKeys.refresh` | `(vfo, reasons: dict[nome, motivo])` | — | Oculta bandas com motivo |
| Sinal `BandKeys.selected(object)` | `Band` | — | |
| `AnalogPanel.set_readings` | `(dbm, audio_level)` | — | VU = 20·log10(nível) |
| `DisplaySettings` sinais | `bandsChanged(list)`, `analogChanged(bool, str)`, `lcdScaleChanged(int)` | — | |
| `dbfs_to_s_units` | `(dbfs, calibration_db=0.0)` | `(dbm, texto)` | |

## Fluxo Principal
1. A engine grava `signal_db` e `signal_sample_time` a cada bloco. 🟢 `engine.py:415-417`
2. O tick confere frescor (< 2,5 s); converte com `dbfs_to_s_units` e chama `set_signal`. 🟢 `ui/main_window.py:2076-2086`
3. O LCD calcula segmentos e pico e repinta. 🟢 `ui/lcd.py:171-185,194`
4. Ao mudar fonte ou VFO, `_band_unsupported` gera motivos e `BandKeys.refresh` reorganiza a grade. 🟢

## Fluxos Alternativos
- **Sem medição:** `set_signal(None, "S--", False)`; pico zerado. 🟢
- **Sem fonte conectada:** motivos estimados pelo tipo de fonte e nome do dispositivo (V4 detectado pelo nome). 🟢 `ui/main_window.py:930-950`
- **Apresentação mínima:** esconde widgets e restaura o estado anterior ao sair. 🟢

## Dependências
- `memory.Band`/`BAND_PLAN`/`band_for` para as teclas de banda. 🟢
- Fonte (`check_freq`, `tuning_range`). 🟢
- Config: `lcd_theme`, `lcd_scale_percent`, `bands_visible`, `analog_enabled`, `analog_style`, `presentation`, `presentation_minimal`, `s_meter_cal`. 🟢

## Decisões de Design Identificadas

| Decisão | Evidência no código | Confiança |
|---------|---------------------|-----------|
| Ocultar bandas incompatíveis em vez de esmaecer (ADR 016) | `ui/bandkeys.py:68-90` | 🟢 |
| Ausência de medição sem barras fixas | `ui/lcd.py:171`, CHANGELOG 0.11.0 | 🟢 |
| LCD desenhado à mão com segmentos (QPainter) | `ui/lcd.py:29-55,194` | 🟢 |

## Estado Interno
LCD: `signal_dbm`, `signal_valid`, `s_text`, `squelch_open`, `_peak`, `_peak_t`, `_preferred_percent`, tema. BandKeys: `visible_names`, `_reasons`, `buttons`. 🟢

## Observabilidade
Tooltip do LCD com dBFS, dBm aproximado e S. 🟢 `ui/main_window.py:2083`

## Riscos e Lacunas
- 🔴 S-meter não calibrado (offset nominal).
- 🔴 LCD e teclas de banda sem homologação visual (BACKLOG).
