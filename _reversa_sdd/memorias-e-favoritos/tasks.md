# Memórias e favoritos, Tarefas de Implementação

## Pré-requisitos
- [ ] Diretório de configuração (ver `idiomas-e-configuracoes`)
- [ ] Sintonia e modo da MainWindow

## Tarefas

- [ ] T-01, `Band`, `BAND_PLAN` e `band_for`
  - Origem no legado: `pt2vhf/memory.py:12-52`
  - Critério de pronto: 145,5 MHz → "2 m"; 300 MHz → None
  - Confiança: 🟢
- [ ] T-02, `MemoryChannel` e `MemoryBank` com JSON
  - Origem no legado: `pt2vhf/memory.py:54-165`
  - Critério de pronto: ida e volta preserva todos os campos
  - Confiança: 🟢
- [ ] T-03, Gravação atômica e load tolerante a JSON corrompido
  - Origem no legado: dívida D4 (`memory.py:114-126`)
  - Critério de pronto: arquivo truncado não impede a abertura e gera backup
  - Confiança: 🟡 (melhoria, não comportamento atual)
- [ ] T-04, Importação e exportação CHIRP
  - Origem no legado: `pt2vhf/memory.py:166-230`
  - Critério de pronto: tabela de modos e tons
  - Confiança: 🟢
- [ ] T-05, Pacotes prontos
  - Origem no legado: `pt2vhf/presets.py`
  - Critério de pronto: 8 pacotes, sem duplicar
  - Confiança: 🟢
- [ ] T-06, Regiões
  - Origem no legado: `pt2vhf/memory_regions.py`
  - Critério de pronto: validação de nome e gravação atômica
  - Confiança: 🟢
- [ ] T-07, Barra de favoritos e chamada de memória
  - Origem no legado: `pt2vhf/ui/listening.py:24-95`, `ui/main_window.py:1210-1222`
  - Critério de pronto: clique chama; menu remove
  - Confiança: 🟢
- [ ] T-08, Pilha por banda
  - Origem no legado: `pt2vhf/ui/main_window.py:985-1015`
  - Critério de pronto: até 3 entradas e alternância
  - Confiança: 🟢
- [ ] T-09, Favoritos em menu suspenso e ordenados por uso (backlog)
  - Origem no legado: não existe
  - Critério de pronto: contador de uso persistido e menu compacto
  - Confiança: 🔴

## Tarefas de Teste

- [ ] TT-01, Banco e pacotes (`tests/test_memory_engine.py`, `tests/test_scanner_presets.py`)
- [ ] TT-02, CHIRP ida e volta
- [ ] TT-03, Regiões (`tests/test_v080_integrations.py`)

## Ordem Sugerida
1. T-01 e T-02.
2. T-04 a T-06.
3. T-07 e T-08, UI.
4. T-03 e T-09 só se aprovados.

## Lacunas Pendentes (🔴)
- Decidir o tratamento de JSON corrompido (backup, aviso).
- Definir "frequência de uso" para ordenar favoritos.
