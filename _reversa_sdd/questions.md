# Perguntas para Validação — PT2VHF SDR Tool

> Gerado pelo Revisor em 28/11/2026. `answer_mode = chat`: as perguntas são feitas na conversa e as respostas registradas aqui.
> Perguntas por unit já existentes: [radiossonda-rs41/questions.md](radiossonda-rs41/questions.md), [atualizacao-ota/questions.md](atualizacao-ota/questions.md).

---

## Pergunta 1

**Contexto:** A extração foi feita na branch `claude/project-thread-hzahgn` (base `main`, `__version__ = "0.13.3"`). A versão publicada é a tag `v1.0.9` (SHA b64aebe), 156 commits à frente, com 58 arquivos alterados em `pt2vhf/`, `scripts/` e `tests/` (novos: `decoders/modes.py`, `decoders/acars.py`, `ais_rx.py`, `dsp/zoom.py`, `sources/mirics.py`, `sources/frequency_translation.py`, `crash_diagnostics.py`, `resource_monitor.py`, `ui/welcome.py`, `ui/acars_panel.py`). A `main` também tem o PR #31 (HF do V4/V4L) que esta branch não tem.
**Spec afetada:** todas, em especial `recepcao-sdr`, `espectro-e-waterfall`, `memorias-e-favoritos`, `trafego-adsb-ais`, `radiossonda-rs41`, `atualizacao-ota`.
**Pergunta:** As specs devem descrever a `main` (v0.13.3) ou a linha publicada v1.0.9?
**Impacto:** Se for a v1.0.9, as units acima precisam de re-extração; vários 🔴 de "backlog não implementado" (favoritos por uso, Auto contínuo, ADS-B/ACARS nativos) passam a 🟢 ou 🟡 e surgem units novas (ACARS, diagnóstico de falhas, monitor de recursos, boas-vindas).

**Resposta:** <!-- pendente -->

---

## Pergunta 2

**Contexto:** `pt2vhf/aprs_igate.py` e `pt2vhf/ui/igate_panel.py` sobraram após a remoção da UI na v0.10.0.
**Spec afetada:** [`igate-aprs/requirements.md`](igate-aprs/requirements.md) RF-03
**Pergunta:** O código órfão do iGate deve ser removido ou mantido como reserva documentada?
**Impacto:** Remover elimina uma capacidade de envio desligada; manter exige um teste que garanta que ela continua fora da UI.

**Resposta:** <!-- pendente -->

---

## Pergunta 3

**Contexto:** `SatellitePanel` é criado (`ui/main_window.py:272`) e ligado a `tune`, mas não entra em nenhuma aba; `TrafficFeedsPanel` (`ui/traffic_panel.py:191`) não é usado.
**Spec afetada:** [`satelites/requirements.md`](satelites/requirements.md) RF-06, [`trafego-adsb-ais/design.md`](trafego-adsb-ais/design.md)
**Pergunta:** Esses painéis devem voltar à interface ou ser removidos?
**Impacto:** Define se RF-06 de satélites fica Could ou sai da spec.

**Resposta:** <!-- pendente -->

---

## Pergunta 4

**Contexto:** `check_updates` está em `DEFAULTS` (`config.py:83`) e não é lido; a verificação automática é controlada por `auto_update` (`ui/assist_panels.py:284`).
**Spec afetada:** [`atualizacao-ota/requirements.md`](atualizacao-ota/requirements.md), [`idiomas-e-configuracoes/requirements.md`](idiomas-e-configuracoes/requirements.md)
**Pergunta:** `check_updates` deve ser removido ou passar a desligar a verificação?
**Impacto:** Muda T-08 de atualizacao-ota e a lista de chaves de DEFAULTS.

**Resposta:** <!-- pendente -->

---

## Pergunta 5

**Contexto:** `decoders/tones.py` detecta CTCSS e DTMF, não DCS.
**Spec afetada:** [`tons-dtmf-ctcss/design.md`](tons-dtmf-ctcss/design.md)
**Pergunta:** DCS é desejado, ou fica explicitamente fora do escopo?
**Impacto:** Se fora de escopo, a lacuna vira 🟢 "não suportado por decisão".

**Resposta:** <!-- pendente -->
