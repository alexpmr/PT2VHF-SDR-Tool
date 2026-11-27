# Redução de ruído neural, Tarefas de Implementação

## Pré-requisitos
- [ ] `pyrnnoise` (opcional; testes usam backend injetado)

## Tarefas

- [ ] T-01, Worker com fila de 8 e descarte do mais antigo
  - Origem no legado: `pt2vhf/neural_audio.py:30-72`
  - Critério de pronto: fila cheia incrementa `dropped`
  - Confiança: 🟢
- [ ] T-02, Processamento em quadros de 480, sobra e mistura por força
  - Origem no legado: `pt2vhf/neural_audio.py:80-106`
  - Critério de pronto: backend falso de identidade devolve a entrada
  - Confiança: 🟢
- [ ] T-03, Fallback em falha e em contagem divergente
  - Origem no legado: `pt2vhf/neural_audio.py:96-140`
  - Critério de pronto: critério de aceitação de falha
  - Confiança: 🟢
- [ ] T-04, Integração na engine
  - Origem no legado: `pt2vhf/engine.py:97-108,419-421`
  - Critério de pronto: recusa → publicação direta
  - Confiança: 🟢
- [ ] T-05, Perfil Sinal fraco
  - Origem no legado: `pt2vhf/ui/main_window.py:1951-1981`
  - Critério de pronto: restauração completa
  - Confiança: 🟢
- [ ] T-06, Homologação com RF real (qualidade, CPU, latência)
  - Origem no legado: CLAUDE.md
  - Critério de pronto: medições registradas por modo
  - Confiança: 🔴

## Tarefas de Teste

- [ ] TT-01, Backend falso e fallback (`tests/test_v012_ai_audio.py`)
- [ ] TT-02, WFM sem tratamento

## Ordem Sugerida
1. T-01 a T-03.
2. T-04 e T-05.
3. T-06.

## Lacunas Pendentes (🔴)
- Protocolo de homologação de áudio neural com RF real.
