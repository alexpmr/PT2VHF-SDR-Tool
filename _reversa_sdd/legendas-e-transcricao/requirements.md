# Legendas e transcrição

## Visão Geral
Reconhecimento de fala local com faster-whisper: **legendas ao vivo** do áudio recebido, num popup só de texto e numa lista exportável, e **transcrição** das gravações por atividade, com destaque de indicativos. Os modelos só são baixados por ação explícita e a inferência é offline. 🟢

## Responsabilidades
- Baixar modelos tiny/base/small sob demanda para a pasta local. 🟢
- Acumular áudio e reconhecer trechos em thread própria. 🟢
- Extrair indicativos do texto. 🟢
- Transcrever arquivos de atividade em fila. 🟢
- Mostrar o popup de legendas e a lista com frequência e modo. 🟢

## Regras de Negócio
- Modelos permitidos: tiny, base, small; caminho `<config>/models/whisper-<tamanho>/`; instalado = `model.bin` e `config.json` presentes. 🟢 `live_caption.py:24-36`
- Download só por clique, em thread `whisper-install`; um download por vez; resultado por evento `caption_model_download`. Download que não gera modelo completo é erro. 🟢 `live_caption.py:38-47`, `ui/main_window.py:1861-1877`
- Inferência: CPU, int8, 4 threads, `local_files_only=True`. 🟢 `live_caption.py:99-104`
- Ligar legendas sem backend ou modelo: desliga o botão, abre Ferramentas > Transcrição e explica como baixar. 🟢 `ui/main_window.py:1885-1899`
- Legendas recebem o áudio tratado (depois de squelch e volume) por `audio_listeners`. 🟢 `ui/main_window.py:1907`
- Trecho de ≥ 4 s (mínimo 2 s); ignora trechos com pico < 0,009; fila de 2, preferindo o mais recente; reamostra para 16 kHz; VAD ligado; beam 1; idioma escolhido ou automático. 🟢 `live_caption.py:53-125`
- Cada legenda leva carimbo de tempo, texto, indicativos, idioma e (VFO, modo) do momento. 🟢 `live_caption.py:63-66,122-123`
- Falta de modelo ou de biblioteca encerra o worker após o aviso. 🟢 `live_caption.py:128-129`
- Indicativos: regex `\b(?:[A-Z]{1,2}[0-9]|[0-9][A-Z])[0-9]?[A-Z]{1,4}\b` sobre o texto em maiúsculas, exigindo um dígito, sem repetir. 🟢 `transcribe.py:16-24`
- Transcrição: liga só com modelo instalado; cada evento `activity` envia o arquivo à fila; resultado `(arquivo, texto, indicativos)`; erro gera texto vazio e guarda `error`. 🟢 `transcribe.py:35-80`, `ui/main_window.py:2132-2135,1926-1943`
- Popup de legendas mostra só texto. 🟢 CLAUDE.md, `tests/test_caption_popup_ui.py`
- Áudio de recepção nunca vai para API externa. 🟢 CLAUDE.md
- 🔴 Qualidade de reconhecimento e de indicativos com RF real não homologada; modelos não vêm pré-baixados.

## Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-01 | Baixar modelo sob demanda | Must | Pasta com `model.bin` e `config.json` |
| RF-02 | Legendas ao vivo | Should | Popup e lista atualizados |
| RF-03 | Destacar indicativos | Should | "PY2ABC" encontrado em "aqui PY2ABC câmbio" |
| RF-04 | Transcrever gravações por atividade | Should | Texto na lista de atividade |
| RF-05 | Exportar legendas em CSV | Could | `LiveCaptionsPanel.export_csv` |
| RF-06 | Escolher idioma ou automático | Should | `live_caption_language` |
| RF-07 | Operar offline | Must | Nenhum acesso à rede após o download |

## Requisitos Não Funcionais

| Tipo | Requisito inferido | Evidência no código | Confiança |
|------|--------------------|---------------------|-----------|
| Privacidade | Download explícito, inferência local | `live_caption.py:38-40,99-104` | 🟢 |
| Responsividade | `feed` só acumula; inferência em thread `legendas-sdr` | `live_caption.py:70-95` | 🟢 |
| Latência | Trechos de 4 s | `live_caption.py:53` | 🟢 |

## Critérios de Aceitação

```gherkin
Dado o modelo tiny não instalado
Quando o operador liga as legendas
Então o botão volta a desligado e aparece a orientação para baixar o modelo

Dado o modelo tiny instalado e legendas ligadas
Quando chegam 4 s de fala
Então surge uma legenda com hora, texto, indicativos, frequência e modo

Dado 4 s de silêncio com pico 0,005
Quando o trecho fecha
Então nada é enviado ao reconhecimento

Dado a transcrição ligada
Quando termina uma gravação por atividade
Então o texto aparece na lista de atividade
```

## Prioridade (MoSCoW)

| Requisito | MoSCoW | Justificativa |
|-----------|--------|---------------|
| Offline e download explícito | Must | Regra de privacidade |
| Legendas, indicativos, transcrição | Should | Recurso opcional |
| Exportação | Could | Conveniência |

## Rastreabilidade de Código

| Arquivo | Função / Classe | Cobertura |
|---------|-----------------|-----------|
| `pt2vhf/live_caption.py` | `ALLOWED_MODELS`, `local_model_path`, `model_installed`, `install_local_model`, `LiveCaptionWorker` | 🟢 |
| `pt2vhf/transcribe.py` | `CALLSIGN_RE`, `find_callsigns`, `backend_available`, `Transcriber` | 🟢 |
| `pt2vhf/ui/live_captions_panel.py` | `LiveCaptionsPanel` | 🟢 |
| `pt2vhf/ui/main_window.py` | `_download_caption_model`, `_toggle_live_captions`, `_toggle_transcription`, `caption_popup` | 🟢 |
| `pt2vhf/app.py` | autoteste confere que faster-whisper e `download_model` estão empacotados, sem baixar nada (`app.py:166-172`) [Revisão: corrigido, não há download por linha de comando] | 🟢 |
