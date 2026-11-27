# Display e instrumentos, Tarefas de Implementação

## Pré-requisitos
- [ ] Engine expondo `status["signal_db"]` e `signal_sample_time`
- [ ] Plano de bandas (ver `memorias-e-favoritos`)

## Tarefas

- [ ] T-01, Conversão dBFS → dBm → S
  - Origem no legado: `pt2vhf/dsp/demod.py:177-188`
  - Critério de pronto: −48 dBFS = −93 dBm = S9; −28 dBFS = S9+20
  - Confiança: 🟢
- [ ] T-02, LCD de segmentos com temas, entrada de frequência e sinais
  - Origem no legado: `pt2vhf/ui/lcd.py`
  - Critério de pronto: digitação, roda e teclas funcionam
  - Confiança: 🟢
- [ ] T-03, S-meter de 40 segmentos com pico de 1,5 s e estado sem medição
  - Origem no legado: `pt2vhf/ui/lcd.py:171-185,355-400`
  - Critério de pronto: `tests/test_v011_lcd.py` passa
  - Confiança: 🟢
- [ ] T-04, Teclas de banda filtradas e compactadas
  - Origem no legado: `pt2vhf/ui/bandkeys.py`, `ui/main_window.py:924-970`
  - Critério de pronto: sem banda fora da faixa do SDR
  - Confiança: 🟢
- [ ] T-05, Medidores analógicos e estilos
  - Origem no legado: `pt2vhf/ui/analog.py`
  - Critério de pronto: S e VU respondem
  - Confiança: 🟢
- [ ] T-06, Configurações de display e escala 50–150%
  - Origem no legado: `pt2vhf/ui/display_settings.py`, `ui/lcd.py:108-117`
  - Critério de pronto: escala persistida
  - Confiança: 🟢
- [ ] T-07, Modo apresentação
  - Origem no legado: `pt2vhf/ui/main_window.py:2212-2260`
  - Critério de pronto: entra e sai restaurando a janela
  - Confiança: 🟢

## Tarefas de Teste

- [ ] TT-01, S-meter sem amostra mostra S-- (`tests/test_v011_lcd.py`)
- [ ] TT-02, Bandas ocultas por fonte
- [ ] TT-03, Limite de escala

## Ordem Sugerida
1. T-01, base.
2. T-02 e T-03.
3. T-04, depende do plano de bandas.
4. T-05 a T-07.

## Lacunas Pendentes (🔴)
- Procedimento de calibração do S-meter com gerador ou sinal de referência.
- Homologação visual do LCD em monitores reais.
