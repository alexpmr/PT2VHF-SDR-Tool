# Investigação P0 — encerramento inesperado no PT2VHF SDR Tool v0.13.3

**Situação:** regressão relatada pelo usuário em 11/11/2026; causa ainda **não identificada**. Não afirmar que o problema foi corrigido apenas porque testes automatizados passaram.

## Mitigação

- A versão v0.13.3 foi temporariamente retirada do catálogo OTA em `alexpmr/PT2VHF-Site/main/updates.json` no commit `20f3dd57e61bc7e42fd8c839970fcd41110b78c7`, voltando a recomendar v0.13.2 até investigar a falha. O deploy Hostinger pode demorar.
- O GitHub Release v0.13.3 permanece disponível para auditoria e rastreabilidade, **mas não deve ser recomendado como estável durante a investigação**.
- Uma instalação já na v0.13.3 não faz downgrade automático. Para reproduzir na v0.13.2, baixar **a mesma modalidade** (Setup ou Portable) do GitHub, salvar antes uma cópia de `%APPDATA%\PT2VHF-SDR-Tool` e não apagar configurações sem backup.
- Não atualizar o catálogo para v0.13.3 nem gerar v0.13.4 sem evidência da falha resolvida.

## Coleta de evidências

A branch `fix/crash-diagnostics-v0133` instrumenta a próxima build de diagnóstico, **não a v0.13.3 já instalada**. A instrumentação grava localmente:

- `%APPDATA%\PT2VHF-SDR-Tool\crash-diagnostics.log`: hora UTC, PID, versão Python, início, encerramento limpo, exceções sem tratamento e traces nativos de `faulthandler` (inclusive all_threads).
- `%APPDATA%\PT2VHF-SDR-Tool\pt2vhf-sdr.log`: log operacional preexistente quando a versão Windows é empacotada sem console.
- Rotação após 2 MiB, mantendo uma cópia `.1`. **Não há telemetria automática, upload ou exposição pública de logs**.

Para a v0.13.3 atual, coletar o log operacional acima e **Monitor de Confiabilidade do Windows** (`perfmon /rel`) ou Visualizador de Eventos → Logs do Windows → Aplicativo. Registrar hora, evento `Application Error`/`Windows Error Reporting`, módulo com falha e código de exceção; remover dados pessoais antes de compartilhar.

## Testes

- `tests/test_crash_diagnostics.py`: startup, anotação de encerramento, registro de exceções, rotação do log e ausência de falha na interface pela instrumentação.
- `tests/test_waterfall_click_to_tune.py`: 120 ciclos de atualização IQ sintética, duplo clique, VFO e centralização em Qt, mantendo zoom.
- CI deve executar Linux Qt e o Windows x64 completo com Setup, Portable, smoke OTA e selftests.
- Probe P0 adicional no Windows: `python -X faulthandler scripts/probe_qt_native_exit.py --repeats 3 --frames 120`. Ele cria subprocessos separados para Qt mínimo e waterfall sintético, testa saída Python normal **e** `os._exit`, confere o código real de término (incluindo `0xC0000005`/`0xC0000374`) e imprime o stderr do processo. Não usa hardware SDR, não cria release e não atribui automaticamente a falha da produção a Qt. Se falhar, comparar primeiro o mesmo probe nas tags v0.13.2 e v0.13.3 e coletar WER/dump antes de alterar o runtime.
- Atenção: `scripts/run_tests.py` usa `os._exit` após o pytest para evitar finalizadores Python/Qt. Um resumo `N passed` não prova que a finalização nativa é segura; por isso o probe independente verifica **exit code** e diferencia saída normal e abrupta.
- A aprovação de CI com sinais sintéticos **não equivale a ensaio de resistência com RTL-SDR/rtl_tcp/SoapySDR físico**. Exigir comparação A/B e reprodução em bancada.

## Hipóteses a investigar — não confirmadas

1. Exceção em callback de Qt, finalizador ou race condition entre GUI e DSP.
2. Falha nativa de biblioteca C/C++ (RTL-SDR, libusb, PortAudio, Qt/PySide6, pyqtgraph ou biblioteca de áudio).
3. Comportamento de atualização/encerramento voluntário em `quit_for_update` (possível somente se a rotina OTA for acionada).
4. Condição específica do hardware, versão do driver, dispositivo SDR ou configuração persistida.

O delta entre as releases v0.13.2 e v0.13.3 é restrito principalmente ao waterfall e tratamento de pacotes OTA; atribuir causa requer logs e testes reais.

Issue de rastreamento: https://github.com/alexpmr/PT2VHF-SDR-Tool/issues/8
