# CLAUDE.md — PT2VHF SDR Tool

Instruções para agentes que trabalham **neste repositório**. Consulte o código e o CI atuais antes de afirmar algo. Idioma de comunicação: português do Brasil; mantenha identificadores técnicos existentes.

## Continuidade operacional — revisão 09/11/2026
- Fonte de verdade: `BACKLOG.md` (seção **Handoff para Claude Code — 09/11/2026**) e CI/artefatos associados à SHA realmente executada.
- **Correção de informação desatualizada deste documento:** a release mais recente registrada é **v0.13.0**, não v0.12.0. O registro de publicação e limitações está em `BACKLOG.md`. OTA de atualização/instalação automática **continua com falha**; não considerar um download manual equivalente.
- **Branch experimental:** PR #2 draft aberto, `feature/iq-signal-classifier`; head consultado `8cc7fb278c0e80a76750256c662b13373d840cc6`. Contém pipeline e testes sintéticos v2–v5. Foi identificado sucesso apenas do workflow geral `Testes (build Windows sob demanda)` run #270 nesse head; a execução/conclusão do workflow `Experimental IQ model training and ONNX export` **não foi verificada** nesta consulta. Consultar Actions e artefatos antes de afirmar que os modelos foram treinados ou validados.
- **Segurança na retomada IQ:** não usar acurácia sintética como homologação RF; validar IQ real rotulado, auditoria, sessões de holdout, OOD/UNKNOWN, WFM (não contemplado no contrato RF 48 kHz), latência e CPU; não alterar o modo/VFO automaticamente. PR separado da main até aceite.
- **Novidade pendente de UI:** clicar no waterfall para sintonizar o ponto; conversão precisa de pixel para Hz com zoom/pan e limites do SDR; teste offscreen e SDR real.
- **Próximos passos:** corrigir OTA P0 e testes Windows; conferir e registrar status real dos jobs de treino/ONNX; depois seguir critérios de aceite de RF e pendências de interface/RS41/S-meter.
- Esta atualização é **apenas documental**: não gera nova release, não inicia treino e não aprova testes não executados.

## Projeto e arquitetura
- Aplicação de recepção SDR **Python >=3.10** (CI: Python 3.12); UI desktop **PySide6/Qt 6.11.3 + pyqtgraph**; DSP com **NumPy/SciPy**; áudio via **sounddevice/PortAudio**.
- Fontes IQ: RTL-SDR/pyrtlsdr, rtl_tcp, SoapySDR, WAV IQ e simulador. Principal entrega binária: **Windows x64** (instalador Inno Setup 6 + portátil PyInstaller); Linux/macOS têm execução a partir do código, não um pipeline de binários homologado neste repo.
- `run_pt2vhf.py` e `pt2vhf/app.py`: pontos de entrada; `pt2vhf/__init__.py`: `__version__`; `pyproject.toml`: metadados/dependências/console script `pt2vhf-sdr`.
- `pt2vhf/sources/`: aquisição IQ e drivers; `pt2vhf/dsp/`: filtragem/demodulação; `pt2vhf/engine.py`: thread de DSP, eventos, gravações, decodificação e distribuição de áudio; `pt2vhf/audio.py`: saída/gravadores.
- `pt2vhf/decoders/`: AFSK/AX.25/APRS, DTMF e CTCSS; `pt2vhf/sonde_rx.py`: pipeline RS41 dependente de ferramentas externas; `pt2vhf/traffic.py`: telemetria e feeds externos ADS-B/AIS/sondas; `pt2vhf/scanner.py`: varredura.
- `pt2vhf/neural_audio.py`: RNNoise; `pt2vhf/live_caption.py` e `transcribe.py`: faster-whisper; `pt2vhf/ui/`: LCD, waterfall, painéis e `main_window.py`; `webserver.py`: painel web/áudio local/LAN; `updater.py`: OTA.
- `pt2vhf/config.py`: configuração JSON persistente em `%APPDATA%\PT2VHF-SDR-Tool` (Windows) ou `~/.config/PT2VHF-SDR-Tool` (Linux); nunca sobrescreva configurações reais do operador em testes.
- Referências: `README.md` (uso/arquitetura), `BACKLOG.md` (pedidos e aceite, nem sempre implementados), `CHANGELOG.md`, `docs/RELEASE_NOTES_*.md`, `tests/` e `.github/workflows/`.

## Fluxo de trabalho e escopo
1. Confira `git status`, branch, código atual, `README.md`, `BACKLOG.md` e workflows pertinentes; parta da branch solicitada. Padrão para manutenção estável: `main`. Não faça merge implícito de branches experimentais.
2. Esclareça no plano se a tarefa é **backlog/documentação**, implementação, validação, build ou publicação. Não confunda essas etapas; não implemente o backlog sem autorização.
3. Faça mudanças mínimas e focadas, preservando funcionalidades, idioma selecionado, dados, compatibilidade e controles. Não altere outros projetos PT2VHF nem gere binários/releases para uma tarefa documental.
4. Trate `README`/`BACKLOG` históricos com cautela: quando houver contradição, confirme o comportamento no código da branch alvo e em testes; novas decisões explícitas do mantenedor prevalecem sobre pedidos antigos.
5. Mantenha aquisição/DSP desacoplados do Qt: **não bloquear** thread RF/áudio com inferência, rede ou gravação; use workers/filas limitadas e entregue eventos à UI pela thread principal. Não manipule widgets Qt a partir de threads de DSP/HTTP.
6. Registre diagnóstico objetivo: modo, fonte, frequência, centro, sample rate, PPM, ganho, SNR/dBFS, estado de squelch, blocos perdidos, erro de backend e logs; isole recepção, processamento, decoder e visualização.

## Execução e testes — comandos efetivos
```bash
python -m pip install -r requirements-dev.txt
python run_pt2vhf.py --sim
python run_pt2vhf.py --debug
python run_pt2vhf.py --selftest
```
- Para rodar sem janela em Linux/CI: `QT_QPA_PLATFORM=offscreen python -X faulthandler scripts/run_tests.py`.
- Para PowerShell/Windows: `$env:QT_QPA_PLATFORM='offscreen'; python scripts/run_tests.py`.
- `python -m pytest -q` também existe na documentação, mas prefira `scripts/run_tests.py` para a suíte completa: ele preserva o retorno do pytest e evita segfault/dupla destruição Qt **após** o teardown.
- Testes de UI: `tests/conftest.py` mantém QApplication única; não abra diálogos modais nem inicie SDR real/autoconexão. Use `QT_QPA_PLATFORM=offscreen`, `PT2VHF_NO_AUTOCONNECT=1`, `PT2VHF_NO_STARTUP_DIALOGS=1`; hardware só em validação controlada.
- Para falhas: reproduza em teste determinístico (sinais sintéticos de `tests/synth_signals.py`, mocks), acrescente regressão e execute a suíte. Testes sintéticos e autotestes **não** substituem teste com RF/SDR real.
- `--selftest` verifica partes da cadeia sem RF, interface e dependências; o executável Windows empacotado faz verificações adicionais. Não declare êxito sem log/exit code.

## Build Windows e CI/CD
- Arquivos: `pt2vhf.spec` (PyInstaller: pasta + executável portátil), `packaging/installer.iss` (Inno Setup 6), `packaging/make_version_info.py` (gera metadados a partir de `__version__`), `build_windows.bat` (atalho local; conferir seus nomes/caminhos contra o workflow).
- Comandos de empacotamento, **somente quando autorizado**: `python packaging/make_version_info.py`, `pyinstaller --noconfirm pt2vhf.spec` e Inno Setup `ISCC.exe /DAppVersion=X.Y.Z packaging\installer.iss`; o CI Windows inclui preparação de drivers, selftest de ambos os .exe, instalação silenciosa, SHA-256 e artefatos.
- `.github/workflows/build.yml`: em push para `main`/PR executa testes Linux/Qt offscreen; o job **windows-exe** só roda em despacho manual com `build_windows=true` ou push cujo título de commit contém **`[build-windows]`**.
- **Atenção:** push em `main` com `[build-windows]` também pode criar automaticamente GitHub Release; não use esse marcador em alterações comuns. Não dispare `release.yml` ou `verify-site.yml` sem pedido explícito.
- `release.yml`: despacho manual para promover build Windows aprovado (run_id/versão e SHA-256). `verify-site.yml`: verificação manual de publicação pública via `scripts/verify_site.py X.Y.Z [--wait]`.
- Versão: mantenha `pt2vhf/__init__.py` e `pyproject.toml` coerentes; `packaging/version_info.txt` é derivado. Não altere número de versão por mudanças só no `CLAUDE.md`.
- **Pipeline ≠ publicação**: teste Linux aprovado, build Windows aprovado, GitHub Release criada, OTA/site implantados e download externo validado são evidências separadas. Site oficial `https://www.pt2vhf.com/sdr`; validar `/update.php?product=sdr`, `/updates.json`, Setup/Portable, tamanho e SHA-256 **no ar**.
- Antes de anunciar versão pronta, confirmar CI da SHA exata, artefatos Windows íntegros, instalação/autoteste no Windows, GitHub Release quando autorizada e manifestação no site/OTA separadamente.

## Segurança e privacidade
- Não inclua segredos, tokens, callsigns privados, coordenadas pessoais, logs sensíveis, dumps IQ/áudio reais ou chaves em commits. Não publicar gravações sem consentimento.
- O SDR Tool é prioritariamente **receptor**; não introduza transmissões RF, APRS-IS/iGate, PTT ou portas abertas por suposição. Respeite limites legais e autorização explícita do operador.
- `webserver.py` disponibiliza áudio/estado por HTTP: acesso LAN pode operar sem chave conforme configuração; **não expor à Internet**, não assumir TLS/autenticação e não alterar defaults de rede sem revisão de segurança.
- OTA (`updater.py`): somente host HTTPS oficial, sem redirecionamento, nomes permitidos, tamanho e SHA-256 obrigatórios. Falha de verificação bloqueia instalação; jamais ignorar assinatura/hash por conveniência.
- Download de pesos Whisper `tiny/base/small` apenas por ação explícita do usuário; execução posterior local/offline. Não enviar áudio de recepção a API externa nem criar telemetria sem consentimento.
- Drivers WinUSB/RTL-SDR Blog e decoders externos (`fsk_demod`/`rs41mod`) requerem diagnóstico, fonte confiável e instalação consciente; nunca executar shell arbitrário ou esconder erros de subprocessos.

## Estados de funcionalidade e critérios de aceite
- **Implementado**: código existe na branch certa. **Testado**: evidência de teste específico + resultado e ambiente. **Homologado**: cenário real (RF/dispositivo/Windows, quando aplicável) aprovado. **Publicado**: instaladores/site/OTA conferidos externamente. Não substituir um estado pelo outro.
- Até a revisão de 09/11/2026: release GitHub mais recente **v0.13.0**. A `main` contém mudanças posteriores de UI não incluídas nessa release: `Decodificação` agrupa ADS-B, Sondas Meteorológicas, AIS e APRS/DTMF/CTCSS; `Ferramentas` concentra transcrição/legendas; popup exibe apenas texto; aba principal Satélites removida, biblioteca orbital preservada.
- RNNoise e faster-whisper têm implementação/testes de software, mas qualidade, latência, CPU e reconhecimento de indicativos com SDR real carecem de homologação; modelos Whisper não vêm pré-baixados.
- **RS41 é P0 aberto**: sinal no waterfall ou quadros sintéticos não demonstram telemetria válida. Exigir captura IQ real, `fsk_demod`/`rs41mod` e prova com serial/frame/posição/altitude no mapa; não marcar funcional sem isso.
- ADS-B/AIS usam feeds/decoders externos; **não** alegar demodulação RF nativa. Tradução automática, SSTV, DMR/D-STAR/C4FM, IQ neural/ONNX e outros itens do backlog não são recursos entregues.
- Branch `feature/iq-signal-classifier` / PR #2: experimental, **não mesclado em `main`**. Não afirmar classificador treinado, validado ou publicado sem evidência atual.
- Sempre mencionar pendências e evidências faltantes; evitar afirmações como “100% do backlog” sem testes e aceites item a item.

## Skills do Claude Code (uso condicional)
- **Neste repositório, nenhuma skill está versionada** em `.claude/skills/`, `.agents/skills/` ou arquivo de índice de skills. Há skills conhecidas no ambiente **local** do mantenedor, mas isso **não comprova** disponibilidade no Claude Code web/nuvem. Verifique as skills efetivamente acessíveis no início da sessão; não invente invocações.
- Conjunto local informado: `android`, `frontend-design`, `skill-creator`, `webapp-testing`, `cicd-expert`, `find-skills`, `ponytail`, `ponytail-audit`, `ponytail-debt`, `ponytail-gain`, `ponytail-help`, `ponytail-review`, `release-manager`, `secure-code-review`, `systematic-debugging`, `test-driven-development`, `verification-before-completion`, `web-design-guidelines`.
- Se acessíveis, usar `systematic-debugging` em bugs difíceis, `test-driven-development` para regressões/novidades, `verification-before-completion` antes de dizer “concluído”, `secure-code-review` para OTA/web/driver/dependências, `cicd-expert` para workflows e `release-manager` **apenas** em lançamento autorizado.
- `webapp-testing`/`web-design-guidelines`: somente para interface web/HTTP; `frontend-design` apenas se aplicável ao fluxo de UI solicitado. `android` pertence a outros projetos, não a este desktop Python. Use `find-skills` se faltar competência e `skill-creator` somente quando for solicitado criar uma skill.
- Se a skill não estiver instalada no executor, trabalhe com os comandos e testes versionados do repositório; nunca alegue que a skill foi aplicada.

## Fechamento de cada tarefa
Informar: arquivos/branch/commit, diff relevante, comandos e resultado dos testes, verificações manuais pendentes e estado exato (**código**, **teste**, **homologação**, **release**, **site**). Não disparar publicação, alteração de driver ou acesso a RF real sem solicitação explícita.
