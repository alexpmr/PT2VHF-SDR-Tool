# IQ/ONNX — relatório de validação sintética (10/11/2026)

**Escopo:** avaliação **sintética**, sem SDR RF real. Não aprova implantação. Fonte de evidência: [GitHub Actions #58](https://github.com/alexpmr/PT2VHF-SDR-Tool/actions/runs/42831768209), commit `343d023eb23fb4fd874228d32a21f1b984494575`, job `train-export-validate` (#129883367357). Artefato [#13771957454](https://github.com/alexpmr/PT2VHF-SDR-Tool/actions/runs/42831768209/artifacts/13771957454), com pesos v2–v5, ONNX, métricas e SHA256SUMS.

## Resultado do pipeline

- **Conclusão da execução #58: SUCCESS**; treinamento/exportação/paridade ONNX v2–v5, stress, OOD, smoke WAV sintético e `147 passed in 3.06s` na suíte específica de IQ.
- Testes adicionados no commit anterior: cinco cenários de IQ constante/DC-only para bloquear falso sinal depois da normalização; incluídos na suíte de 147 aprovada.
- Validação sintética interna da v2: 5.600 amostras de treino, 1.400 de validação, acurácia **0,9914285714**. Não extrapolar para RF real.
- Exportação ONNX: paridade numérica de 31 casos confirmada nos logs; máximo erro absoluto observado v3 **0,00001526**, v4 **0,00001144**, v5 **0,00000763**.
- Artefato ZIP SHA-256: `9d0465c2bfa49cb701886e7c8a0ae74d1dace285bf9189457680632c7dcd2cd2`.

## Comparação fora da família de geração original

Amostras **sintéticas** com SNR 0/6/12/20 dB, sinais conhecidos e negativos OOD. WFM **não** foi avaliado. Aceitação indevida de OOD usa limiar de confiança **0,80**.

| Modelo | Top-1 | Erro com confiança alta | ECE (10 bins) | Falsa aceitação OOD |
|---|---:|---:|---:|---:|
| v2 | 0,699 | 0,223 | 0,235 | 0,491 |
| v3 | 0,697 | 0,250 | 0,250 | 0,906 |
| v4 | **0,768** | **0,144** | **0,148** | **0,197** |
| v5 | 0,637 | 0,230 | 0,265 | 0,212 |

### Fragilidades importantes

- v4 é a melhor **neste conjunto**, mas não é homologada: falsa aceitação de `unmodulated_carrier` = **0,775**; recall CW por SNR 0/6/12/20 dB = **0,35 / 0,30 / 0,15 / 0,15**; recall AM = **0,75 / 0,60 / 0,375 / 0,475**.
- v3 tem falsa aceitação OOD de **0,906** e `impulsive_noise` = **1,000**: não promover com base na boa acurácia em dados semelhantes ao treinamento.
- v5 piora acurácia geral (0,637), sem redução suficiente de OOD frente à v4; não promover.
- Em v4 a elevação do limiar 0,80 → 0,999 reduz falsa aceitação OOD de 0,197 para 0,116, mas reduz sinais conhecidos corretamente aceitos de 0,634 para 0,347. Um único limiar não resolve o problema.
- Teste de rejeição de IQ constante **não** implica rejeição de portadora senoidal não modulada com frequência deslocada: são entradas distintas.

## Portões de aceitação futuros

1. Coletar IQ de **RF real** rotulado independentemente (CW/AM/NFM/USB/LSB/UNKNOWN) em sessões, locais/dispositivos e SNR variados; não comitar WAV privados.
2. Aplicar auditoria de integridade, prevenção de vazamento entre sessões e holdout independente. Documentar parâmetros de captura, downconversion e taxa 48 kS/s.
3. Medir matriz de confusão, recall por classe, taxa de aceitação indevida de OOD, calibração, latência/CPU e descarte de frames. Separar portadoras reais de artefatos DC usando verificação externa.
4. Reavaliar arquitetura/dataset para CW/AM e OOD de portadora, preferindo avaliação fora de distribuição em vez de ajuste por acurácia de treino.
5. WFM exige contrato e amostragem compatíveis com sua largura de banda: não reivindicar cobertura com holdout estreito 48 kHz.
6. Manter PR #2 experimental: inferência não altera VFO/modo automaticamente; não empacotar/publicar modelo como pronto antes da homologação RF.

**Próximo passo recomendado:** preparar protocolo de coleta RF e registrar evidências externas, antes de iniciar outra rodada de treinamento sintético.

## Rodada posterior: execução #59 — 10/11/2026

- [Workflow #59](https://github.com/alexpmr/PT2VHF-SDR-Tool/actions/runs/42834956654): **SUCCESS**, commit `f8557cd3517099a3544984ed45746fa84e21d752`.
- `148 passed in 2.66s`: teste adicional de consistência de denominadores e curvas de aceitação OOD aprovado; modelos sintéticos v2–v5 exportados e paridade ONNX confirmada (31 casos por exportação).
- [Artefato #13773641510](https://github.com/alexpmr/PT2VHF-SDR-Tool/actions/runs/42834956654/artifacts/13773641510), 702.569 bytes, ZIP SHA-256 `95ad810ebb1cc1860abec670ed29e11df5d61acdc3017779fdf67e46bfbf268f`.
- **Métricas independentes inalteradas** em relação à #58: v2 0,699 top-1 / 0,491 OOD; v3 0,697 / 0,906; v4 0,768 / 0,197; v5 0,637 / 0,212, com limiar 0,80. Portadora não modulada na v4 ainda tem falsa aceitação de **0,775**.
- A melhoria desta rodada é na **confiabilidade dos testes**, não na generalização do modelo. Não confundir pipeline verde com release ou homologação RF.
- **Decisão:** manter bloqueio de implantação; não iniciar sucessivos treinamentos sintéticos sem novo desenho de experimento e conjunto de RF real independente. Prioridade é o protocolo de captura/etiquetagem e erro por classe CW/AM/UNKNOWN.

## Rodada #62 — duas sementes independentes (10/11/2026)

- [GitHub Actions #62](https://github.com/alexpmr/PT2VHF-SDR-Tool/actions/runs/42835992077): **SUCCESS**, commit `6a0dc320260cc16da0f530db68feaba97317f71c`; **149 testes aprovados**; arquivo de métricas da segunda semente incluído no artefato [#13774915706](https://github.com/alexpmr/PT2VHF-SDR-Tool/actions/runs/42835992077/artifacts/13774915706).
- Seeds: `20261112` (referência reproduzida na #62) e `20261113` (nova avaliação). Gerador sintético `scripts/iq_out_of_family.py`; sem WFM, sem IQ RF real.
- **Importante:** as métricas de referência da execução #62 não são idênticas às anteriormente relatadas para #58/#59. Comparar as duas sementes **dentro da mesma execução #62**, com os mesmos pesos, em vez de tratar resultados de execuções diferentes como mera variação da semente.

| Modelo | Top-1 seed 20261112 | Top-1 seed 20261113 | Delta (p.p.) | Portadora OOD seed 1 | Portadora OOD seed 2 |
|---|---:|---:|---:|---:|---:|
| v2 | 68,3% | 69,7% | +1,4 | 97,5% | 100,0% |
| v3 | 69,9% | 69,9% | 0,0 | 85,0% | 88,7% |
| v4 | **76,4%** | **75,0%** | **−1,4** | **75,0%** | **83,8%** |
| v5 | 71,3% | 69,9% | −1,4 | 75,0% | 85,0% |

- A v4 preserva o melhor top-1, mas classifica erroneamente **60/80 e 67/80** portadoras não moduladas como classes conhecidas com confiança ≥ 0,80 nos dois conjuntos; diferença de 7 casos (8,75 p.p., arredondado 8,8). **Bloqueio para integração operacional permanece**.
- Amostra de negativos por família é pequena (80 por seed) e deriva do mesmo desenho de gerador. **Duas sementes não fornecem intervalo de confiança amplo nem garantia de generalização**. Repetir seeds sem novos perfis físicos não substitui avaliação RF.
- Diferenças entre execuções do treinamento precisam de investigação de determinismo dos pesos, versionamento e ambiente; comparação de seeds é válida quando mantém fixos pesos e parâmetros. Não promover modelo baseado apenas no ranking deste teste.
- **Próxima decisão:** antes de treinar outra versão, coletar IQ RF real rotulado por operador, particionado por sessões/dispositivos, e medir CW, AM, UNKNOWN e portadoras OOD com taxas e intervalos de confiança; relatório experimental deve guardar hashes dos pesos e origem do dataset.


## Investigação complementar — primeiro passo integral em float64 (hipótese, ainda sem resultado)

O diagnóstico `scripts/diagnose_iq_cpu_step.py` agora replica **somente o primeiro minibatch** em uma cópia independente da rede, convertida integralmente para `float64`. São registrados hashes SHA-256 de pesos iniciais, logits, perda, gradientes e pesos após **um** passo Adam. O comparador informa a primeira divergência desse caminho em campo próprio, **sem suprimir** a divergência original do treino `float32`.

Hipótese testável: se a divergência entre CPUs estiver restrita à implementação `float32`, o passo integral `float64` poderá ser idêntico em processadores distintos. Mesmo que isso se confirme, **não demonstra** reprodutibilidade após 22 épocas, desempenho/latência aceitável ou homologação RF real. O caminho de treinamento e o modelo ONNX de produção não foram alterados. Aguardar CI e comparar somente runners efetivamente heterogêneos.

O comparador retorna falha de diagnóstico também quando **apenas** o passo integral float64 diverge; essa divergência não pode ser ocultada pelo sucesso do caminho float32. `first_divergent_stage` preserva a primeira divergência original; `first_divergent_float64_stage` identifica separadamente a divergência do controle.



## Diagnóstico direcionado do Adam (instrumentação experimental)

O probe de primeiro minibatch passa a registrar, **sem modificar o treinamento v4**, os hashes dos estágios de uma atualização Adam de referência escrita explicitamente em float64: primeiro e segundo momentos, raiz quadrada do segundo momento, denominador, atualização normalizada e pesos propostos. Também são registrados hashes por tensor dos pesos propostos e dos pesos efetivamente atualizados pelo Adam do PyTorch. A referência manual é **somente diagnóstica**: sua ordem de operações pode diferir do kernel nativo, mesmo no mesmo processador. O comparador mantém separadas as divergências do forward, do Adam manual e dos parâmetros nativos; falha se qualquer uma divergir entre CPUs. O índice do primeiro tensor divergente é relatado sem expor pesos. A instrumentação não equivale a reprodutibilidade de 22 épocas nem a RF real.



## Hipótese seguinte: erro em ULP na raiz quadrada do Adam (instrumentação; resultado pendente)

O diagnóstico do primeiro minibatch float64 agora compara **até 256 segundos momentos positivos por tensor** com um oráculo independente: raiz quadrada `Decimal` em 110 dígitos decimais, convertida para `float64`. Registra SHA-256 das amostras nativas e do oráculo, quantidade de amostras, divergências, erro máximo em ULP e a primeira posição divergente. O comparador exige a mesma quantidade de amostras e mantém o gate de identidade exata; não altera tolerâncias nem treinamento. Os hashes completos dos tensores continuam sendo verificados.

**Hipótese:** se os hashes do oráculo coincidirem entre CPUs, mas os nativos divergirem, a diferença de `torch.sqrt` fica sustentada por referência independente, e o erro em ULP pode ser quantificado. Amostragem esparsa **não** demonstra identidade de todos os elementos nem determinismo em 22 épocas. Nenhuma captura RF ou homologação é inferida. Aguardar workflow heterogêneo antes de concluir.


## Gate de CPU heterogênea — correção fail-closed (11/11/2026)

O comparador `scripts/compare_iq_cpu_step.py` já identificava `SAME_CPU_ONLY_INCONCLUSIVE` quando ambos os runners usavam o **mesmo modelo de CPU**, mas o CLI encerrava com código **0**, deixando o workflow diagnóstico verde apesar de não testar portabilidade entre CPUs. O CLI agora retorna **3** para esse caso, preservando `comparison.json` e os artefatos do workflow (`if: always()`). Retorna **2** para `NUMERICAL_DIVERGENCE` ou `ENVIRONMENT_MISMATCH`, e **0** somente quando os primeiros passos coincidem em modelos de CPU diferentes. Testes sintéticos exercitam o CLI e os três caminhos de decisão; o código 0 **não comprova** a reprodutibilidade do treinamento completo de 22 épocas.

A atribuição de CPUs em runners hospedados pelo GitHub não é controlada pelo workflow: se os dois runners forem homogêneos, a falha é **inconclusiva**, não um defeito do modelo. Um diagnóstico heterogêneo com resultados iguais continua sendo apenas evidência limitada aos primeiros passos, não homologação de RF, OOD, Windows, latência ou implantação.


## 12/11/2026 — mecanismo de saída Windows e A/B de runtime (CI #43168113474)

- [GitHub Actions #43168113474](https://github.com/alexpmr/PT2VHF-SDR-Tool/actions/runs/43168113474): Linux **381 passed / 2 skipped**; Windows reportou **381 passed / 2 skipped** seguido de `Windows fatal exception: access violation`; o wrapper fail-closed marcou **failure**. Nenhum instalador neural foi gerado.
- O diagnóstico de encerramento executou dois casos UI em subprocessos isolados. `os._exit` falhou em **2/2** com diagnóstico nativo; saída normal passou **2/2** e `TerminateProcess` passou **2/2** nessa execução. Esses resultados não demonstram a causa raiz; `TerminateProcess` ignora finalização de DLLs e **não é correção nem critério de QA**. A saída normal também apresentou corrupção de heap em execuções anteriores.
- **Nova hipótese falsificável, sem treinamento:** o crash pode depender da combinação de versões Python/PySide6. A matriz experimental compara Python **3.11/3.12** e PySide6 **6.9.3/6.11.3**, em dois testes UI isolados com `os._exit`, preservando a detecção de exceções nativas. É um teste diagnóstico, não homologação; resultados ainda pendentes.
- Os jobs de diagnóstico de encerramento sem pytest, teardown e mecanismo de saída, já investigados, foram removidos do disparo automático para evitar repetir medições inalteradas; scripts históricos permanecem no repositório. O job principal Windows continua obrigatório, sem mascaramento. Nenhum dado IQ RF real foi fornecido.

## CI Windows — matriz de runtime 3.11/3.12 × PySide6 6.9.3/6.11.3 (12/11/2026, ~05h BRT)

Fonte: [GitHub Actions #43177095139](https://github.com/alexpmr/PT2VHF-SDR-Tool/actions/runs/43177095139), branch experimental. Os quatro jobs `windows-qt-runtime-probe` **falharam**, todos com `Windows fatal exception: access violation` após `1 passed` em **cada um dos dois casos UI isolados** (`test_main_navigation_and_lcd_band_theme` e `test_reconnects_receiver_on_start`). Resultado: **8/8 combinações caso × runtime com falha nativa**; nenhuma das quatro combinações de versões resolveu o encerramento neste ensaio. Isso não identifica a DLL culpada e não exclui interações com pytest, Qt ou bibliotecas de terceiros.

A suíte Linux reportou **381 passed / 2 failed / 2 skipped**; a suíte Windows também reportou **381 passed / 2 failed / 2 skipped**, seguida de access violation. As duas falhas de asserção foram `IndexError` em `tests/test_iq_windows_exit_mechanism_probe.py` e `tests/test_iq_windows_exit_probe.py`: verificavam a presença de jobs de CI históricos já removidos intencionalmente. Trata-se de **regressão dos testes de guarda do workflow**, independente da falha nativa. Correção exclusiva na branch experimental: commits [`5df5032`](https://github.com/alexpmr/PT2VHF-SDR-Tool/commit/5df5032aa097478bf6de111ea16115daf011cfd5) e [`0a24222`](https://github.com/alexpmr/PT2VHF-SDR-Tool/commit/0a2422222b429d6566829bb8b756aac2160a118e), substituindo asserções obsoletas por verificação explícita de que os jobs antigos não são agendados e de que o diagnóstico ativo permanece isolado da release. **Validação CI dos novos commits ainda não confirmada** no momento do registro.

`windows-file-probe` manteve os mesmos dois arquivos UI com falha nativa; `windows-exe` permaneceu **skipped** e nenhum artefato neural foi produzido nesta execução. A matriz 2×2 é uma hipótese testada e falsificada para essas versões; não repetir a mesma matriz sem novo fator causal. A próxima investigação deve capturar pilha nativa/minidump de processo em Windows e verificar o ciclo de vida dos objetos Qt/pytest sem neutralizar a detecção fail-closed.

**Gates inalterados:** RF real com rótulos independentes, AMD × Intel v4, OOD/UNKNOWN e CW/AM, latência/CPU e Windows sem exceções nativas. Não mesclar PR #2, não alterar `main`, não treinar novamente sem hipótese, não gerar/publicar instalador neural.

**Controle de custo após falsificação da hipótese:** o job automático 2×2 foi desativado no commit [`c5301c7`](https://github.com/alexpmr/PT2VHF-SDR-Tool/commit/c5301c710dc8b1f06a6034b320c2543f48e720b4), preservando as evidências e os diagnósticos por arquivo/caso. Os testes de guarda foram alinhados à remoção nos commits [`8a75049`](https://github.com/alexpmr/PT2VHF-SDR-Tool/commit/8a75049cc0c4a56613b150367cca60ee0699ca2e) e [`8c62fe3`](https://github.com/alexpmr/PT2VHF-SDR-Tool/commit/8c62fe359266502ba9eed39fdb36fdadc1e9aa5a). Nenhum resultado de CI posterior é inferido a partir dessa alteração.

## Rodada de diagnóstico Windows — 12/11/2026, ~06h55 BRT

- **Regressão adicional identificada por inspeção estática:** `tests/test_iq_windows_runtime_matrix.py` ainda exigia o job `windows-qt-runtime-probe`, embora a matriz 2×2 já tivesse sido aposentada após reproduzir 8/8 falhas nativas no [CI #43177095139](https://github.com/alexpmr/PT2VHF-SDR-Tool/actions/runs/43177095139). O teste foi atualizado para exigir a **ausência** do job e preservar os guards do `windows-file-probe`. A alteração remove uma asserção obsoleta; não é uma correção da corrupção de memória.
- **Nova hipótese de diagnóstico:** o Windows Error Reporting (WER) pode registrar um minidump local e/ou um evento `Application Error` (ID 1000) ou `Windows Error Reporting` (ID 1001) contendo módulo e código da exceção, permitindo restringir a causa nativa sem repetir matrizes de versões ou atrasos.
- O job `windows-tests` agora configura `HKCU\\...\\LocalDumps\\python.exe` com `DumpType=1` (minidump), `DumpCount=3`, em `RUNNER_TEMP`, antes de executar o mesmo gate `scripts/ci_windows_pytest.py`. **Somente após falha**, informa quantidade/tamanho/SHA-256 dos dumps e eventos WER recentes associados a Python/PT2VHF. Os arquivos `.dmp` **não são enviados como artefatos**, porque podem conter memória e informações sensíveis; desaparecem com o runner efêmero. Não há download de símbolos nem análise de pilha nativa automática nesta etapa.
- Adicionados guards estáticos para impedir upload acidental de dumps e verificar que a checagem fail-closed e o isolamento de release foram preservados. **O resultado no Windows do novo HEAD ainda não foi confirmado**: a instrumentação é tentativa de coleta, não evidência de minidump obtido nem de causa identificada.
- Se não houver dump/evento, registrar explicitamente a ausência e avaliar instrumentação com depurador nativo em uma hipótese nova. Não converter ausência de registro em aprovação de QA.
- Gates de RF real independente, AMD × Intel, OOD/UNKNOWN, CW/AM, CPU/latência e Windows permanecem fechados. PR #2 draft; sem merge, `main`, instalador neural ou publicação.


## Windows CI #445 — 12/11/2026, 07h40–08h50 BRT (evidência pós-commit)

- [Run #43202372696](https://github.com/alexpmr/PT2VHF-SDR-Tool/actions/runs/43202372696) no HEAD `4609b37`: Linux **392 passed / 2 skipped**, job concluído com sucesso. Windows também completou **392 passed / 2 skipped**, mas imprimiu `Windows fatal exception: access violation` imediatamente após o resumo, com traceback de `scripts/run_tests.py` linha 38 (`os._exit`); o gate fail-closed **reprovou corretamente** o job. Contagem de testes aprovados não equivale a QA nativo aprovado.
- WER: **nenhum minidump** de `python.exe` e **nenhum evento correspondente** 1000/1001 foi obtido no runner. Isso não identifica a DLL, não demonstra ausência de corrupção de memória e não permite aprovação Windows. O job `windows-exe` permaneceu **skipped** e a execução não produziu artefatos.
- O subconjunto Windows IQ/hard-exit foi aprovado isoladamente nessa execução; os subconjuntos não-IQ, a suíte completa e os probes de UI continuam falhando. Isso não prova causalidade nem inocenta o código neural.
- **Nova hipótese econômica, ainda não validada:** testar se a falha está associada ao plugin QPA `offscreen` do Qt. Somente o job diagnóstico `windows-case-probe` passa a usar `QT_QPA_PLATFORM=minimal`, com os mesmos casos UI e saída `hard`. O job principal Windows **permanece offscreen e fail-closed**. A mudança altera apenas um fator de plataforma, não o classificador nem a release. Se `minimal` apresentar falhas de funcionalidades Qt não suportadas, separar falha pytest funcional de `Windows fatal exception`; um resultado limpo em casos isolados não libera o gate Windows completo. Não repetir esta comparação em novos ciclos sem hipótese adicional.
- O treinamento v2–v5 permanece exclusivamente manual; nenhuma captura RF genuína com rótulos independentes foi apresentada. Permanecem fechados os gates AMD × Intel v4, OOD/UNKNOWN, CW/AM, RF real, latência/CPU, Windows e instalador/update. PR #2 draft, sem merge, `main` ou publicação neural.


## CI #43213137478 — hipótese QPA minimal versus offscreen (12/11/2026)

- [GitHub Actions #43213137478](https://github.com/alexpmr/PT2VHF-SDR-Tool/actions/runs/43213137478), HEAD experimental `2a168499`: Linux **392 passed / 2 skipped**, concluído com sucesso; Windows **392 passed / 2 skipped**, mas com `Windows fatal exception: access violation` após o resumo e gate **failure**. Nenhum instalador neural ou artefato foi produzido.
- No job `windows-case-probe` com `QT_QPA_PLATFORM=minimal`, **4/9** casos isolados em `hard exit` falharam com diagnóstico nativo (código 86): `test_main_navigation_and_lcd_band_theme`, `test_reconnects_receiver_on_start`, `test_simulator_is_not_reconnected`, `test_top_tabs_header_and_levels`. São os mesmos quatro casos que falharam em `hard exit` sob `offscreen` no [CI #440](https://github.com/alexpmr/PT2VHF-SDR-Tool/actions/runs/43195868516), embora as execuções não sejam um experimento pareado com ambiente absolutamente idêntico.
- **Resultado negativo:** mudar apenas o plugin Qt para `minimal` não eliminou o defeito nos casos reproduzidos. Não atribuir a causa ao QPA, ao ONNX ou a uma DLL específica sem pilha nativa. O job automático dessa hipótese foi aposentado para evitar repetição de custo; o script manual continua disponível. A suíte Windows principal permanece obrigatória, `offscreen` e **fail-closed**.
- **Gates sem alteração:** não há IQ RF genuíno com rótulos independentes; AMD × Intel v4 diverge; OOD/UNKNOWN, CW/AM e latência operacional continuam sem aprovação; Windows nativo segue reprovado. Nenhum retreino, merge, alteração em `main` ou publicação da IA foi autorizado por esta evidência.


## Windows Qt DeferredDelete A/B — 12/11/2026 (hipótese encerrada)

- [CI #43245498976](https://github.com/alexpmr/PT2VHF-SDR-Tool/actions/runs/43245498976): Linux **404 passed / 2 skipped**; Windows obrigatório **404 passed / 2 skipped**, mas **access violation** em `os._exit`, gate reprovado. A primeira execução A/B abortou em `sendPostedEvents(DeferredDelete)` **dentro** do teste que invoca `run_tests.main()` aninhado. Esse resultado não era comparação válida de encerramento pós-pytest.
- O diagnóstico revelou a propagação indevida da variável `PT2VHF_CI_QT_DISPOSE_AFTER_PYTEST` aos testes de runner simulados. Corrigidos três testes e adicionado guard no runner para nunca descartar Qt durante `PYTEST_CURRENT_TEST`, com teste de regressão; instrumentadas fases agregadas de descarte. Nenhuma mudança no job Windows obrigatório ou no runtime do usuário.
- [CI #43248657060](https://github.com/alexpmr/PT2VHF-SDR-Tool/actions/runs/43248657060): Linux **405 passed / 2 skipped**, aprovado. Windows obrigatório **405 passed / 2 skipped**, seguido de **access violation** em `os._exit`; WER sem minidump/evento. Census antes de pytest: 1 thread Python, 4 threads nativas, Qt não inicializado; após pytest e antes do hard exit: 1 thread Python, 16 threads nativas, **666 widgets Qt top-level, todos ocultos**. Isso é contagem de recursos, **não** prova vazamento, retenção indevida ou causa do crash.
- No A/B corrigido, o mesmo conjunto concluiu **405 passed / 2 skipped**; `deleteLater()` foi solicitado para **666 widgets**, com **zero exceções Python** durante a fila. A chamada subsequente `QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)` abortou nativamente (`Fatal Python error: Aborted`) **antes** de `app.processEvents()` e antes do census pós-descarte. Portanto **não** foi demonstrada a redução dos widgets nem a prevenção do crash. A limpeza forçada em massa é, ela própria, insegura nesse estado; isso **não identifica a DLL nem prova que os widgets causaram o access violation original**.
- O job `windows-qt-disposal-probe` foi **aposentado** após o A/B válido para não repetir custo nem provocar novos abortos automaticamente. O guard Windows obrigatório permanece **fail-closed**. Próxima hipótese útil requer pilha nativa/módulo por depurador ou isolamento de propriedade/tempo de vida de objetos, sem publicar dumps ou dados de memória. Evitar novas matrizes Python/PySide6/QPA e não mascarar a falha com `TerminateProcess`.

**Sem alteração dos gates:** AMD × Intel v4, OOD/UNKNOWN, CW/AM, CPU/latência e RF real com rótulos independentes continuam pendentes. Não houve treinamento pesado, merge, alteração na `main`, instalador neural ou publicação no site.


## Diagnóstico v4 entre fabricantes de CPU — revisão 12/11/2026, 23h BRT

**Hipótese metodológica:** o comparador de quatro passos distinguia apenas
`cpu_model` por string. Duas máquinas Intel com modelos diferentes poderiam
receber `FIRST_STEPS_MATCH_CROSS_CPU_NOT_FULL_REPLAY` e exit 0, embora
não representassem a comparação **AMD × Intel** requerida. Além disso,
`cpu_capability` era coletado pelo probe mas não integrava a checagem de
paridade de ambiente, permitindo que backends CPU distintos fossem tratados
como comparáveis.

**Correção experimental:** `scripts/compare_iq_cpu_step.py` agora registra
`reference_cpu_vendor`, `independent_cpu_vendor` e `cross_vendor_tested`.
O sucesso limitado a quatro passos requer fabricantes reconhecidos e
diferentes (AMD e Intel). Modelos distintos do mesmo fabricante resultam em
`SAME_VENDOR_ONLY_INCONCLUSIVE`; fabricante não reconhecido resulta em
`CPU_VENDOR_UNKNOWN_INCONCLUSIVE`. Ambos retornam exit 3, sem falso
resultado positivo. Divergência de `cpu_capability` agora resulta em
`ENVIRONMENT_MISMATCH` (exit 2). Foram acrescentados testes sintéticos
de classificação de fabricantes, controle positivo e negativos de ambiente.

**Custo/escopo:** o workflow `iq-cpu-step-diagnostic.yml` passou a exigir
`workflow_dispatch` explícito, pois dois runners `ubuntu-latest` não
garantem um par AMD/Intel. A suíte regular continua testando o comparador.
Não executar nova reprodução de 22 épocas nem novos probes caros sem acesso
a dois hosts com fabricantes comprovados e hipótese numérica específica.

**Limites:** a inferência do fabricante pelo nome informado pelo sistema
não é atestado de hardware; os dados podem ser mascarados por VM. Mesmo um
match de quatro passos AMD/Intel não comprova reprodução integral de 22
épocas nem qualidade ONNX/RF. A divergência v4 permanece **não resolvida**.
Não houve captura RF real, treinamento, merge ou publicação neural.
