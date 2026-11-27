# Recepção SDR, Tarefas de Implementação

## Pré-requisitos
- [ ] NumPy disponível; pyrtlsdr e DLLs librtlsdr para hardware real
- [ ] Engine capaz de consumir `read()` (ver `demodulacao-e-audio`)
- [ ] Chaves de configuração da fonte documentadas (ver `idiomas-e-configuracoes`)

## Tarefas

- [ ] T-01, Criar `IQSource` com fila de 32, `_push` com descarte do mais antigo e `read(timeout)`
  - Origem no legado: `pt2vhf/sources/base.py:14-98`
  - Critério de pronto: teste enche a fila e confirma `dropped` e ordem dos blocos
  - Confiança: 🟢
- [ ] T-02, Calcular o tamanho de bloco por taxa
  - Origem no legado: `pt2vhf/sources/base.py:39-42`
  - Critério de pronto: 2,4 MS/s → 114688; 240 kS/s → 16384
  - Confiança: 🟢
- [ ] T-03, Implementar `tuning_range` e `check_freq` com a tabela de sintonizadores e a mensagem de HF
  - Origem no legado: `pt2vhf/sources/rtlsdr_source.py:149-162,425-435`
  - Critério de pronto: casos E4000, FC0012, FC2580, R820T, V4 Blog e amostragem direta
  - Confiança: 🟢
- [ ] T-04, Thread de controle com `_submit` e vigia com `STALL_S`, `CMD_TIMEOUT_S` e `MAX_RECOVER`
  - Origem no legado: `pt2vhf/sources/rtlsdr_source.py:165-533`
  - Critério de pronto: dongle simulado que trava passa por recovering, ok e failed
  - Confiança: 🟢
- [ ] T-05, Carregar a biblioteca Blog com stubs e fallback para a padrão
  - Origem no legado: `pt2vhf/sources/rtlsdr_source.py:31-136`
  - Critério de pronto: DLL sem dithering não falha na abertura
  - Confiança: 🟢
- [ ] T-06, `RtlTcpSource` e `SoapySource` com o mesmo contrato de erro do RTL
  - Origem no legado: `pt2vhf/sources/network_sources.py:17-205`
  - Critério de pronto: fora da faixa, as três fontes têm o mesmo comportamento (decidir entre False e exceção)
  - Confiança: 🟡 (corrige a dívida D2)
- [ ] T-07, `SimulatorSource` e `WavIQSource` (centro fixo)
  - Origem no legado: `pt2vhf/sources/sim_sources.py:24-250`
  - Critério de pronto: `--sim` funciona e WAV IQ não aceita retune
  - Confiança: 🟢
- [ ] T-08, Detecção e instalação WinUSB com um UAC
  - Origem no legado: `pt2vhf/sources/rtl_driver.py`
  - Critério de pronto: só a interface 0 é alterada; erro do processo elevado aparece ao operador
  - Confiança: 🟢
- [ ] T-09, `Engine._retune` com margem, offset fs/8 e fallback para centro fixo
  - Origem no legado: `pt2vhf/engine.py:206-226`
  - Critério de pronto: 145,5 MHz a 2,4 MS/s gera centro 145,8 MHz
  - Confiança: 🟢

## Tarefas de Teste

- [ ] TT-01, Fluxo feliz com `SimulatorSource` (`tests/test_sources.py`)
- [ ] TT-02, Recuperação e falha definitiva (`tests/test_rtlsdr_robust.py`)
- [ ] TT-03, Frequência fora da faixa nas três fontes de hardware
- [ ] TT-04, Detecção de WinUSB com interfaces simuladas (hoje sem teste)

## Ordem Sugerida
1. T-01 e T-02, base de todas as fontes.
2. T-07, para testar a engine sem hardware.
3. T-03, T-04 e T-05, o RTL-SDR real.
4. T-06 e T-09 juntos, porque o contrato de erro afeta o retune.
5. T-08 por último; só Windows.

## Lacunas Pendentes (🔴)
- Decidir o contrato único de `set_center_freq` fora da faixa.
- Decidir se o limite de UI deve vir de `check_freq` da fonte em vez de 24 kHz–1766 MHz fixos.
- Validar o watchdog em rtl_tcp e SoapySDR com falha real.
