# APRS e packet, Tarefas de Implementação

## Pré-requisitos
- [ ] Áudio bruto NFM a 48 kHz (ver `demodulacao-e-audio`)
- [ ] `dsp.filters`

## Tarefas

- [ ] T-01, CRC-16/X.25, codificação e decodificação de endereços, `build_frame` e `parse_frame`
  - Origem no legado: `pt2vhf/decoders/ax25.py:7-96`
  - Critério de pronto: ida e volta de um quadro; FCS errado → None
  - Confiança: 🟢
- [ ] T-02, HDLC: bits, NRZI e deframer com bit stuffing
  - Origem no legado: `pt2vhf/decoders/ax25.py:98-160`
  - Critério de pronto: quadro gerado é recuperado
  - Confiança: 🟢
- [ ] T-03, `AFSKDemodulator` com 5 fatiadores e deduplicação de 2 s
  - Origem no legado: `pt2vhf/decoders/afsk.py`
  - Critério de pronto: quadro de `afsk_modulate` decodificado uma vez
  - Confiança: 🟢
- [ ] T-04, Interpretação APRS por tipo
  - Origem no legado: `pt2vhf/decoders/aprs.py:12-229`
  - Critério de pronto: um teste por tipo
  - Confiança: 🟢
- [ ] T-05, Distância, rumo e Maidenhead
  - Origem no legado: `pt2vhf/decoders/aprs.py:232-270`
  - Critério de pronto: valores conferidos com referência
  - Confiança: 🟢
- [ ] T-06, Histórico e mapa HTML
  - Origem no legado: `pt2vhf/aprs_map.py`
  - Critério de pronto: limites de estações e pontos; escape aplicado
  - Confiança: 🟢
- [ ] T-07, Integração na engine e na UI
  - Origem no legado: `pt2vhf/engine.py:403-407`, `ui/main_window.py:2111-2116`
  - Critério de pronto: só em NFM com o decoder ligado
  - Confiança: 🟢

## Tarefas de Teste

- [ ] TT-01, Decodificação sintética (`tests/test_decoders.py`)
- [ ] TT-02, FCS inválido
- [ ] TT-03, Escape do mapa e da web (`tests/test_webserver.py`)

## Ordem Sugerida
1. T-01 e T-02.
2. T-03.
3. T-04 e T-05.
4. T-06 e T-07.

## Lacunas Pendentes (🔴)
- Medir taxa de decodificação com RF real.
