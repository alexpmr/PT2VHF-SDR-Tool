# Tráfego ADS-B e AIS, Tarefas de Implementação

## Pré-requisitos
- [ ] Decodificadores externos para teste manual (opcional)

## Tarefas

- [ ] T-01, `Track` com validação
  - Origem no legado: `pt2vhf/traffic.py:22-53`
  - Critério de pronto: lat 91 levanta `ValueError`
  - Confiança: 🟢
- [ ] T-02, `parse_adsb` com conversões e filtros
  - Origem no legado: `pt2vhf/traffic.py:55-88`
  - Critério de pronto: critério de aceitação de unidades
  - Confiança: 🟢
- [ ] T-03, `parse_radiosondes` tolerante a formatos
  - Origem no legado: `pt2vhf/traffic.py:91-133`
  - Critério de pronto: os quatro formatos aceitos
  - Confiança: 🟢
- [ ] T-04, `AISDecoder` com checksum, fragmentos e tipos 1/2/3/5/18/19
  - Origem no legado: `pt2vhf/traffic.py:136-245`
  - Critério de pronto: mensagem de 2 fragmentos decodificada
  - Confiança: 🟢
- [ ] T-05, `load_traffic` com limites de 2 MB e 8 MB
  - Origem no legado: `pt2vhf/traffic.py:248-271`
  - Critério de pronto: limites testados
  - Confiança: 🟢
- [ ] T-06, Exportações
  - Origem no legado: `pt2vhf/traffic.py:273-360`
  - Critério de pronto: GPX/KML válidos e escapados
  - Confiança: 🟢
- [ ] T-07, `SourceTab` com atualização de 5 s
  - Origem no legado: `pt2vhf/ui/traffic_panel.py:22-190`
  - Critério de pronto: auto liga e desliga
  - Confiança: 🟢

## Tarefas de Teste

- [ ] TT-01, Parsers (`tests/test_v080_integrations.py`)
- [ ] TT-02, Limites de tamanho
- [ ] TT-03, Escape nas exportações

## Ordem Sugerida
1. T-01 a T-05.
2. T-06.
3. T-07.

## Lacunas Pendentes (🔴)
- Decidir se ADS-B/ACARS nativos entram nesta linha de código ou só na v1.x.
- Remover ou ligar `TrafficFeedsPanel`.
