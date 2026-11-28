# Relatório de Confiança — PT2VHF SDR Tool

> Gerado pelo Revisor em 28/11/2026, sobre a branch `claude/project-thread-hzahgn` (base `main`, v0.13.3).

---

## Resumo Geral

Contagem dos marcadores nas 20 units (65 arquivos), sem contar as notas de revisão.

| Nível | Quantidade | Percentual |
|-------|-----------|------------|
| 🟢 CONFIRMADO | 948 | 89,4% |
| 🟡 INFERIDO   | 44 | 4,1% |
| 🔴 LACUNA     | 69 | 6,5% |
| **Total**     | 1061 | 100% |

**Confiança geral:** 91% (🟢 + metade dos 🟡).

⚠️ A confiança mede o quanto as specs batem com o código **desta base**. A versão publicada (v1.0.9) diverge bastante; ver Pergunta 1.

---

## Por Spec

| Spec | 🟢 | 🟡 | 🔴 | Confiança |
|------|----|----|-----|-----------|
| `aprs-packet` | 53 | 1 | 2 | 96% |
| `assistente-de-sintonia` | 45 | 1 | 2 | 95% |
| `atualizacao-ota` | 44 | 8 | 7 | 81% |
| `cat-rigctl` | 42 | 2 | 2 | 93% |
| `demodulacao-e-audio` | 68 | 1 | 2 | 96% |
| `display-e-instrumentos` | 45 | 0 | 4 | 92% |
| `espectro-e-waterfall` | 53 | 1 | 5 | 91% |
| `gravacao-e-timeshift` | 53 | 2 | 1 | 96% |
| `idiomas-e-configuracoes` | 41 | 9 | 0 | 91% |
| `igate-aprs` | 31 | 1 | 4 | 88% |
| `legendas-e-transcricao` | 46 | 2 | 4 | 90% |
| `memorias-e-favoritos` | 53 | 3 | 7 | 87% |
| `painel-web` | 49 | 5 | 2 | 92% |
| `radiossonda-rs41` | 50 | 1 | 8 | 86% |
| `recepcao-sdr` | 63 | 4 | 4 | 92% |
| `reducao-de-ruido-neural` | 37 | 0 | 4 | 90% |
| `satelites` | 42 | 1 | 3 | 92% |
| `scanner-e-ocupacao` | 56 | 2 | 2 | 95% |
| `tons-dtmf-ctcss` | 32 | 0 | 2 | 94% |
| `trafego-adsb-ais` | 45 | 0 | 4 | 92% |

---

## Lacunas Pendentes 🔴

Detalhadas em [gaps.md](gaps.md). Resumo:
- **Base da extração** — specs na v0.13.3, produto publicado na v1.0.9. `questions.md#pergunta-1`
- **Homologação com RF e Windows real** — 11 units dependem de teste com hardware; nenhuma resposta por chat resolve.
- **Decisões do mantenedor** — iGate órfão, painéis órfãos, `check_updates`, DCS. `questions.md#pergunta-2` a `#pergunta-5`

---

## Recomendações

- [ ] Decidir a base (Pergunta 1) antes de usar as specs para reimplementar ou evoluir.
- [ ] `radiossonda-rs41` e `atualizacao-ota` têm os P0 abertos; priorizar a homologação real.
- [ ] `memorias-e-favoritos` — tratar JSON corrompido na abertura (risco de o programa não abrir).
- [ ] Unificar `check_updates`/`auto_update` e levar as chaves soltas para `DEFAULTS` (D8).

---

## Revisão Cruzada
- Engine externa consultada: nenhuma (plugin do Codex indisponível nesta sessão).

---

## Histórico de Reclassificações

| De | Para | Afirmação | Evidência |
|----|------|-----------|-----------|
| 🟡 | 🟢 | SoapySDR importado sob demanda | `sources/network_sources.py:121` |
| 🟡 | 🟢 | Engine só trata `False` de `set_center_freq` | `engine.py:189,220` |
| 🟡 | 🟢 | RNNoise desliga o backend após falha e segue sem tratamento | `neural_audio.py:131-138` |
| 🟡 | 🟢 | `SatellitePanel` fora das abas | `ui/main_window.py:272,618` |
| 🟡 | 🟢 | `TrafficFeedsPanel` órfão | `ui/traffic_panel.py:191` |
| 🟡 | 🟢 | OTA adiado durante scanner e varredura | `ui/main_window.py:1450-1453` |
| 🟡 | 🟢 | Painéis de memórias em `panels.py` | `ui/panels.py:571,636` |
| 🟡 | 🟢 | Faixa do CAT é a dívida D3 | `ui/main_window.py:1525` |
| 🟡 | 🟢 (corrigido) | `app.py` não baixa modelos; só confere o empacotamento no autoteste | `app.py:166-172` |
| 🟡 | 🟢 (corrigido) | Painel do scanner fica em `ui/listening.py`, não em `panels.py` | `ui/listening.py:170` |
