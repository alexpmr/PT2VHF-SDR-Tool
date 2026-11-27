# Scanner e ocupação, Design Técnico

## Interface

| Símbolo | Assinatura | Retorno | Observação |
|---------|-----------|---------|------------|
| `SpectrumScanner.__init__` | `(engine, cfg: ScannerConfig)` | — | `engine` expõe `hold_center`, `set_center`, `tune`, `center_freq`, `sample_rate` |
| `SpectrumScanner.start` / `stop` | `(now=0.0)` / `()` | — | Prende e solta o centro |
| `SpectrumScanner.feed` | `(spec, center, fs, now)` | `list[tuple]` | Eventos: `("hit", Hit, novo)`, `("listen", f)`, `("priority", f)`, `("resume", f)`, `("segment", c, i, n)` |
| `SpectrumScanner.lockout` | `(freq)` | — | Remove o acerto |
| `sorted_hits` / `channels_per_second` | `()` | `list[Hit]` / `float` | |
| `detect_signals` | `(spec_db, center, fs, f0, f1, resolution, snr_db, usable=0.85, dc_guard_hz=3000, gap_bins=2)` | `(list[Detection], piso)` | |
| `level_at` | `(spec_db, center, fs, freq, half_bw)` | `float \| None` | |
| `OccupancyHistory` | `(path=None)` | — | `record`, `matrix(limit=80)`, `prune`, `clear`, `flush(force)` |

Estados do scanner em `state-machines.md` §2.

## Fluxo Principal
1. `start` calcula os segmentos e chama `_next_segment` → `_goto_center` → `engine.set_center` → `settle`. 🟢
2. Cada linha de espectro (no tick da UI) vai para `feed`; linhas de outro centro são descartadas. 🟢
3. `settle` conta linhas; `dwell` acumula max-hold; ao fim, `_finish_dwell` detecta, atualiza acertos e decide entre prioridade, escuta ou próximo segmento. 🟢
4. A UI transforma eventos em linhas da tabela, marcadores no waterfall e registros de ocupação. 🟢 `ui/main_window.py:2053-2069`
5. Varredura de memórias: `QTimer` chama `_scan_tick`, que usa `status["sq_open"]`. 🟢

## Fluxos Alternativos
- **Faixa num só segmento já centrado:** volta direto a `dwell` sem retunar. 🟢 `scanner.py:213-219`
- **Prioridade fora do segmento:** salta para p + fs/8 e depois retorna ao centro salvo. 🟢
- **Arquivo de ocupação corrompido:** histórico zerado sem erro. 🟢 `occupancy.py:26-30`
- **Frequência fora de 24 kHz–2 GHz na ocupação:** `ValueError`. 🟢

## Dependências
- Engine (`wf_lines`, `set_center`, `tune`, `hold_center`). 🟢
- `MemoryBank` para a varredura de memórias. 🟢
- Config: `scan_dwell_ms`, `scan_resume_s`. 🟢

## Decisões de Design Identificadas

| Decisão | Evidência no código | Confiança |
|---------|---------------------|-----------|
| Scanner por FFT com centro preso (ADR 003) | `scanner.py` | 🟢 |
| Centróide de potência para a frequência do acerto | `scanner.py:90-93` | 🟢 |
| Ocupação conta detecções, deduplicadas por minuto | `occupancy.py:52-65` | 🟢 |
| Escrita atômica só para ocupação | `occupancy.py:96-98` | 🟢 |

## Estado Interno
Scanner: `state`, `running`, `hits`, `_segments`, `_seg`, `sweeps`, `_target_center`, `_lines`, `_maxhold`, `floor_db`, `listen_freq`, `_cooldown`, `_last_priority`, `_resume_center`. Ocupação: `_hours`, `_seen`, `_dirty`, `_last_save`. Varredura de memórias: dict `self.scan` com `items`, `i`, `t`, `held`, `lost`, `dwell`, `resume`. 🟢

## Observabilidade
Contadores `sweeps` e `channels_per_second`; flag `SCAN` no LCD. 🟢

## Riscos e Lacunas
- 🟡 O comentário do squelch automático diz mediana, mas o código usa o quartil inferior.
- 🟡 O OTA é adiado enquanto o scanner ou a varredura de memórias rodam (ver `atualizacao-ota`).
- 🔴 Desempenho real de detecção com RF real e antenas diferentes não está documentado.
