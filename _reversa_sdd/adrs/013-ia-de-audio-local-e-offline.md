# ADR 013: Ia de audio local e offline

- **Status:** Aceito (retroativo)
- **Data/origem:** 2026-11-08 (v0.12.0; ff86932)

## Contexto
Redução de ruído e transcrição ajudam o operador, mas áudio de recepção não deve sair da máquina.

## Decisão
RNNoise (pyrnnoise) e faster-whisper rodam localmente; pesos Whisper tiny/base/small só baixam por ação explícita; falha do backend cai em fallback seguro sem derrubar o áudio; inferência fora da thread RF.

## Evidência
🟢 CHANGELOG 0.12.0; commit ff86932; `pt2vhf/neural_audio.py`, `live_caption.py`, `transcribe.py`.

## Consequências
Privacidade preservada; qualidade, CPU e latência 🔴 não homologadas com RF real.
