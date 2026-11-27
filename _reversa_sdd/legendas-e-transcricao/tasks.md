# Legendas e transcrição, Tarefas de Implementação

## Pré-requisitos
- [ ] `faster-whisper` instalado
- [ ] Diretório de config com `models/`

## Tarefas

- [ ] T-01, Caminho, verificação e download explícito do modelo
  - Origem no legado: `pt2vhf/live_caption.py:24-47`
  - Critério de pronto: tamanho desconhecido levanta `ValueError`
  - Confiança: 🟢
- [ ] T-02, `find_callsigns`
  - Origem no legado: `pt2vhf/transcribe.py:16-24`
  - Critério de pronto: exige dígito; sem repetição
  - Confiança: 🟢
- [ ] T-03, `LiveCaptionWorker` com acúmulo, limiar de silêncio e fila de 2
  - Origem no legado: `pt2vhf/live_caption.py:50-140`
  - Critério de pronto: modelo falso injetado devolve texto
  - Confiança: 🟢
- [ ] T-04, `Transcriber` em fila
  - Origem no legado: `pt2vhf/transcribe.py:35-80`
  - Critério de pronto: erro gera texto vazio e `error`
  - Confiança: 🟢
- [ ] T-05, UI: download, ligar/desligar, popup, lista e exportação
  - Origem no legado: `pt2vhf/ui/main_window.py:1861-1943`, `ui/live_captions_panel.py`
  - Critério de pronto: `tests/test_caption_popup_ui.py` passa
  - Confiança: 🟢
- [ ] T-06, Homologação com RF real
  - Origem no legado: CLAUDE.md
  - Critério de pronto: taxa de acerto de indicativos medida
  - Confiança: 🔴

## Tarefas de Teste

- [ ] TT-01, Worker e transcriber com modelo falso (`tests/test_v012_ai_audio.py`)
- [ ] TT-02, Popup só de texto (`tests/test_caption_popup_ui.py`)
- [ ] TT-03, Nenhum download sem clique

## Ordem Sugerida
1. T-01 e T-02.
2. T-03 e T-04.
3. T-05.
4. T-06.

## Lacunas Pendentes (🔴)
- Protocolo de avaliação com áudio real (sem publicar gravações sem consentimento).
