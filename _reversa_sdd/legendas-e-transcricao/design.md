# Legendas e transcrição, Design Técnico

## Interface

| Símbolo | Assinatura | Retorno | Observação |
|---------|-----------|---------|------------|
| `local_model_path` / `model_installed` | `(size)` | `Path` / `bool` | `ValueError` para tamanho desconhecido |
| `install_local_model` | `(size)` | `Path` | Usa `faster_whisper.utils.download_model` |
| `LiveCaptionWorker` | `(on_result, on_error=None, sample_rate=48000, seconds=4.0, model_size="tiny", language=None, model=None, meta_provider=None)` | — | `feed(audio)`, `stop()` |
| `on_result` | `(timestamp, texto, indicativos, idioma, meta)` | — | `meta = (vfo, modo)` |
| `Transcriber` | `(on_result, model_size="small", language="pt", model=None)` | — | `submit(path)`, `stop()`, `error` |
| `find_callsigns` | `(text)` | `list[str]` | |
| `LiveCaptionsPanel` | `(cfg)` | — | `add_caption(...)`, `export_csv()`, `refresh_model_status()`, `set_downloading(bool)`, sinal `downloadRequested(str)` |
| Eventos | `live_caption`, `caption_error`, `caption_model_download`, `transcription` | — | |

## Fluxo Principal
1. Clique em "Baixar modelo" → thread de download → evento de resultado → painel atualiza o status. 🟢
2. Ligar legendas cria o worker e o registra em `engine.audio_listeners`; o popup aparece. 🟢
3. `feed` acumula; a cada ≥ 4 s com sinal, enfileira com carimbo e meta. 🟢
4. A thread reamostra, transcreve e chama `on_result`, que vira evento para a UI. 🟢
5. Transcrição: eventos `activity` → `submit(arquivo)` → evento `transcription`. 🟢

## Fluxos Alternativos
- **Fila cheia:** troca pelo trecho mais novo. 🟢
- **Modelo ausente na hora da inferência:** `FileNotFoundError`, aviso e fim do worker. 🟢
- **Desligar legendas:** remove o ouvinte, para o worker, esconde e limpa o popup. 🟢

## Dependências
- `faster-whisper` ≥ 1.2, < 2.0; SciPy `resample_poly`. 🟢
- Config `live_caption_model`, `live_caption_language`, `live_caption_enabled`. 🟢

## Decisões de Design Identificadas

| Decisão | Evidência no código | Confiança |
|---------|---------------------|-----------|
| IA local e offline (ADR 013) | `live_caption.py:38-40` | 🟢 |
| Popup só de texto | CLAUDE.md | 🟢 |
| Legendas no áudio tratado, não no bruto | `ui/main_window.py:1907` | 🟢 |

## Estado Interno
Worker: `_chunks`, `_pending_samples`, `_queue`, `_model`. Transcriber: `_q`, `_model`, `error`. UI: `caption_worker`, `transcriber`, `_model_downloading`. 🟢

## Observabilidade
`log.warning` em falhas; evento `caption_error`; status do modelo no painel. 🟢

## Riscos e Lacunas
- 🔴 Qualidade com RF real e reconhecimento de indicativos.
- 🟡 A origem do download (Hugging Face) é inferida da biblioteca.
- 🟡 A regex de indicativos pode gerar falsos positivos em palavras com dígitos.
