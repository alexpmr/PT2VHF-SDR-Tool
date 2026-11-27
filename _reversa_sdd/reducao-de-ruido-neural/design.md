# Redução de ruído neural, Design Técnico

## Interface

| Símbolo | Assinatura | Retorno | Observação |
|---------|-----------|---------|------------|
| `NeuralAudioWorker` | `(on_audio, on_error=None, strength=0.8, backend=None, max_pending=8)` | — | Inicia a thread |
| `feed` | `(audio, mode="NFM")` | `bool` | False = parado ou recusado |
| `stop` | `()` | — | |
| `queue_depth`, `dropped`, `processed_frames` | — | — | Métricas |
| `backend_available` | `()` | `bool` | pyrnnoise instalado |
| `Engine.set_neural_audio` | `(enabled, strength=0.8)` | — | Troca o worker |
| Evento | `("neural_error", texto, ts)` | — | |

## Fluxo Principal
1. A engine, com worker ativo, chama `feed(audio, modo)` em vez de publicar. 🟢
2. A thread pega o bloco; se voz e backend, junta com a sobra, processa múltiplos de 480 e guarda a sobra. 🟢
3. Converte para int16, chama `denoise_chunk`, mistura e chama `on_audio` (= `_publish_audio`). 🟢

## Fluxos Alternativos
- **Não é voz:** devolve a sobra + bloco sem tratamento. 🟢
- **Backend falhou:** devolve o bloco original e desliga o backend. 🟢
- **Nenhum quadro saiu:** devolve o original (nunca mudo). 🟢

## Dependências
- `pyrnnoise` 0.4.5 (opcional). 🟢

## Decisões de Design Identificadas

| Decisão | Evidência no código | Confiança |
|---------|---------------------|-----------|
| IA local, offline, com fallback (ADR 013) | `neural_audio.py`, commit ff86932 | 🟢 |
| Fila com descarte em vez de acumular atraso | `neural_audio.py:31-35` | 🟢 |

## Estado Interno
`_tail`, `_tasks`, `_stop`, `_backend`, `strength`, contadores. Perfil: `_weak_restore`. 🟢

## Observabilidade
`log.warning`, evento `neural_error`, contadores. 🟢

## Riscos e Lacunas
- 🔴 Homologação de qualidade, CPU e latência com RF real.
- 🟡 Depois de uma falha o backend fica desligado até recriar o worker.
