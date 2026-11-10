# PT2VHF SDR Tool — protocolo de validação IQ em RF real

**Status:** procedimento preparado, **não executado com RF real**. Registro em 10/11/2026. O protocolo não autoriza a publicação de modelos nem o merge do PR #2.

## Evidência anterior

- [Actions #64](https://github.com/alexpmr/PT2VHF-SDR-Tool/actions/runs/42843259635): **SUCCESS** nos jobs `train-export-validate` e `verify-v4-across-runners`; **149 testes aprovados**.
- Reexecução da v4 em **dois runners Linux/CPU independentes**, com Python 3.11.18, PyTorch 2.15.0+cpu, NumPy 2.4.6 e duas threads: `parameter_exact_match=true`, `metrics_exact_match=true`, diferença máxima dos pesos **0.0**.
- Artefato experimental #13776459028 e relatório independente #13778170194. Isso prova apenas repetibilidade no ambiente controlado; desempenho RF e WFM permanecem sem validação.
- Dados sintéticos fora da distribuição mostram falsos positivos graves na v4: 75,0% e 83,8% de portadoras não moduladas reconhecidas como classes conhecidas com confiança ≥0,80 em duas sementes; top-1 76,4%/75,0%.

## Requisitos da coleta

1. Utilizar **SDR** com gravação I/Q complexa, em **WAV estéreo PCM16** (I canal esquerdo, Q direito); não gravar áudio demodulado ou MP3.
2. Anotar **dispositivo, data/hora, frequência central da captura, frequência do sinal, taxa de amostragem, ganho/AGC, antena, modo comprovado e sessão**. O rótulo deve ser atribuído pelo operador, não pelo classificador.
3. Registrar **CW com portadora e chaveamento verificável**, **AM**, **NFM**, **USB**, **LSB** e **UNKNOWN** (ruído, portadora sem modulação, interferência e sinais fora das classes); para portadora não modulada, verificar com referência independente que não é espúrio DC do receptor.
4. Fazer **ao menos três sessões independentes** e usar **ao menos dois SDRs diferentes**, conforme aviso já implementado no avaliador. Esse é um mínimo de cobertura operacional, **não** uma garantia estatística.
5. Dividir treino, ajustes de limiar e avaliação **por sessão e dispositivo**, evitando que segmentos da mesma transmissão apareçam em conjuntos diferentes. Nunca treinar em dados reservados para avaliação cega.
6. Guardar os WAVs RF brutos e o manifesto **fora do GitHub**; não incluir identificadores pessoais nem conteúdo de comunicações particulares nos relatórios públicos. Confirmar licitude/consentimento quando necessário.

## Preparar as gravações — comandos existentes no repositório

Executar a partir da raiz do projeto, com um ambiente Python contendo as dependências do SDR Tool. Substituir os caminhos e frequências pelos da coleta, mantendo a gravação de entrada fora da pasta de resultados.

```bash
python scripts/prepare_iq_rf_capture.py \
  --input "/dados/iq_bruto/rf_001.wav" \
  --output "/dados/iq_48k/nfm_sessao01.wav" \
  --center-hz 145500000 \
  --target-hz 145512500 \
  --mode NFM \
  --device "RTL-SDR-V4" \
  --session "sessao01" \
  --root "/dados/iq_48k" \
  --manifest "/dados/iq_48k/manifest.json"
```

A ferramenta converte/centraliza o canal para **48 kS/s** e acrescenta sua identificação ao `manifest.json`. Se a gravação possuir sidecar `.iq.json` íntegro, `--center-hz` pode ser dispensado; conferir integridade e metadados. O exemplo é **apenas ilustrativo**, não informa que a estação ou a frequência foram de fato capturadas.

## Auditoria de qualidade e vazamento

```bash
python scripts/audit_iq_dataset.py \
  --manifest "/dados/iq_48k/manifest.json" \
  --root "/dados/iq_48k" \
  --out "/dados/iq_relatorios/qa.json"
```

- `BLOCK`: corrigir antes de usar o arquivo; o comando retorna código 2.
- `REVIEW`: avaliação humana obrigatória do problema sinalizado.
- `PASS`: nenhum problema listado foi detectado; **não comprova origem RF, rotulagem ou desempenho do modelo**.
- A auditoria detecta janelas idênticas entre sessões, mas não identifica todas as cópias modificadas, vazamentos ou rótulos incorretos.

## Avaliação comparativa dos modelos, sem alterar o SDR

Baixar os pesos ONNX experimentais dos artefatos de Actions em um ambiente local, sem integrá-los ao instalador:

```bash
python scripts/evaluate_iq_recordings.py \
  --manifest "/dados/iq_48k/manifest.json" \
  --root "/dados/iq_48k" \
  --model "models/iq/synthetic_v4.onnx" \
  --additional-model "v2=models/iq/synthetic_v2.onnx" \
  --additional-model "v3=models/iq/synthetic_v3.onnx" \
  --additional-model "v5=models/iq/synthetic_v5.onnx" \
  --max-windows 100 \
  --out "/dados/iq_relatorios/comparativo.json"
```

O parâmetro `--max-windows` seleciona até 100 janelas IQ **não sobrepostas e uniformemente distribuídas ao longo de cada WAV** (incluindo início e fim), em vez de considerar apenas os primeiros segundos. Isso reduz o viés temporal de início de gravação, mas continua sendo uma amostragem determinística limitada; transmissões curtas entre janelas podem não ser observadas. Para ensaios de sensibilidade temporal, aumentar o limite e documentar a cobertura.

Revisar matriz de confusão, recall por classe (em especial CW/AM), erros de alta confiança, curva de aceitação de UNKNOWN, cobertura de sinais conhecidos, acurácia média por sessão e latência/uso de CPU medidos separadamente. O script calcula um intervalo exploratório de confiança por bootstrap de sessões (descrito abaixo), mas **não** calcula latência nem uso de CPU operacional: medir esses indicadores separadamente. A matriz de confusão e o recall utilizam a decisão efetiva do classificador, inclusive o limiar configurado para UNKNOWN; a curva de aceitação aplica cada limiar de forma independente sobre as probabilidades brutas. Não confundir as duas políticas.

## Portões para revisão do PR

- Documentar origem, proveniência e conferência independente de rótulos; validar que o dataset não entrou no treinamento.
- Avaliar classes e OOD por **sessão**, **dispositivo** e **faixa de SNR**; exigir relatório de incerteza e não apenas média por janela altamente correlacionada.
- Sinalizar explicitamente **WFM não validado** no contrato atual: 48 kS/s/2.048 amostras não é evidência para broadcast FM convencional.
- Bloquear decisão automática de VFO/modo até teste operacional supervisionado.
- **Sem gravações RF reais disponíveis, o status da IA permanece EXPERIMENTAL**, mesmo com todos os workflows verdes.

## Intervalo de confiança por sessão (atualização de 10/11/2026)

O script `evaluate_iq_recordings.py` inclui `session_macro_accuracy_ci95`, um intervalo exploratório de 95% por **bootstrap de sessões**, e `session_accuracy_summary` (mínimo, máximo e contagem, sem nomes/IDs de sessão). O cálculo exige **ao menos três sessões** e retorna `null` quando houver menos, evitando apresentar janelas altamente correlacionadas como observações independentes. A sequência aleatória é determinística para auditoria; 2.000 reamostragens por padrão.

**Limitação essencial:** intervalo bootstrap não corrige rótulos errados, viés de seleção, dependência entre sessões, ausência de diversidade de SDR nem prova desempenho operacional.

### Evidência do CI #66 — 10/11/2026

- [GitHub Actions #66](https://github.com/alexpmr/PT2VHF-SDR-Tool/actions/runs/42845233390), commit [`bdcdc17`](https://github.com/alexpmr/PT2VHF-SDR-Tool/commit/bdcdc178ca8422571818ddd9280c6ad5e0eb6319): **SUCCESS** nos dois jobs `train-export-validate` e `verify-v4-across-runners`.
- Suíte IQ: **151 testes aprovados**. Inclui os testes sintéticos de `session_macro_accuracy_ci95` e privacidade do relatório, sem WAV de RF real. Exportação ONNX v2–v5 e `sha256sum -c SHA256SUMS` aprovados no job principal.
- Replay v4 em runner independente com Python 3.11.18, PyTorch 2.15.0+cpu, NumPy 2.4.6 e 2 threads: `parameter_exact_match=true`, `metrics_exact_match=true`, `max_parameter_absolute_difference=0.0`. Esta é reprodutibilidade de treinamento em ambientes Linux/CPU equivalentes, **não** validade em RF.
- [Artefato de modelos #13779095475](https://github.com/alexpmr/PT2VHF-SDR-Tool/actions/runs/42845233390/artifacts/13779095475), 706.252 bytes, digest do ZIP `sha256:dcd68a72e9f24bc1a098c901a262cf29c8a655c23118769430af042fa91eafe0`; [relatório cross-runner #13777273055](https://github.com/alexpmr/PT2VHF-SDR-Tool/actions/runs/42845233390/artifacts/13777273055), 466 bytes, digest do ZIP `sha256:fab55c1b1c61dd6c7c18d56706bfe01735e49b295dcdfccede31f637bce7eefc`.
- Avisos não bloqueantes de depreciação Node.js 20 nas actions; atualizar actions em manutenção separada, sem confundir com erro do classificador.

**Próximo portão:** obter corpus IQ RF real independente, executar auditoria de qualidade e comparar v2–v5 por sessão/dispositivo e classe (CW, AM, UNKNOWN, portadora não modulada). CI verde e bootstrap sobre dados sintéticos **não** autorizam merge, modelo operacional nem release.

### Diagnóstico de CI #65 e contrato de rejeição UNKNOWN (10/11/2026)

- [Actions #65](https://github.com/alexpmr/PT2VHF-SDR-Tool/actions/runs/42845185047), commit `3afa297`: falhou na etapa antecipada de teste RF porque `python -m pytest` foi executado **antes** da instalação de `pytest` (`No module named pytest`). Não foi falha de treinamento nem de ONNX. O commit `bdcdc17` removeu essa etapa duplicada e manteve os testes na etapa existente, após instalar as dependências; [#66](https://github.com/alexpmr/PT2VHF-SDR-Tool/actions/runs/42845233390) passou com 151 testes.
- Auditoria adicional do avaliador offline: `IQClassifier.predict` aplica `min_confidence` e pode retornar `mode="UNKNOWN"` mesmo quando a maior probabilidade bruta pertence a AM/CW/etc. A matriz de confusão e a acurácia por sessão devem usar **`result.mode`**, enquanto a curva de limiares deve usar o argmax bruto sob cada limiar. Misturar os dois inflava erros de UNKNOWN e distorcia recall. Regressão coberta por stubs sintéticos, **sem RF real**.

### Experimento cross-CPU após a falha #68 (10/11/2026)

A [execução #68](https://github.com/alexpmr/PT2VHF-SDR-Tool/actions/runs/42858152704) falhou no replay independente v4; o job principal passou 153 testes IQ, ONNX v2–v5 e SHA-256. Dados e parâmetros iniciais idênticos, mas pesos finais diferentes (diferença máxima 1,4822826385) entre AMD EPYC 9V45 e EPYC 7763. A divergência surge durante a otimização; a operação exata ainda é desconhecida.

**Hipótese a testar:** diferenças no despacho de kernels vetorizados/oneDNN/MKL e no paralelismo. O modo experimental `--portable-cpu` da v4 desativa oneDNN, usa uma thread e algoritmos determinísticos; os jobs definem `ATEN_CPU_CAPABILITY=default` e `MKL_CBWR=COMPATIBLE` antes da importação do PyTorch. A política é registrada nas métricas. Os pesos v4 serão diferentes dos anteriores e exigirão nova comparação de desempenho. **Não presumir sucesso antes de um replay independente concluído.** Se falhar, registrar hashes de gradientes e parâmetros após o primeiro passo do Adam.

Os novos testes unitários verificam a ativação e os pré-requisitos da política, **não** a identidade entre CPUs. Nenhum resultado homologa RF real nem resolve falsos positivos OOD.

### Resultado do experimento portable CPU — #69 (10/11/2026)

[Actions #69](https://github.com/alexpmr/PT2VHF-SDR-Tool/actions/runs/42866405772): **FAILURE** no replay independente, embora o job principal tenha passado **155 testes IQ**, exportação ONNX v2–v5 (opset 18, 31 verificações de paridade/modelo), SHA-256 e replay no mesmo runner. `training_input_exact_match=true`, `initial_parameters_exact_match=true`, mas `parameter_exact_match=false`, `metrics_exact_match=false`, diferença máxima **1,1162637472**. CPUs: referência AMD EPYC 7763, independente Intel Xeon Platinum 8573C; versões Python 3.11.18, PyTorch 2.15.0+cpu, NumPy 2.4.6 e 1 thread coincidem.

**Conclusão:** a política portable CPU não garantiu identidade dos pesos entre arquiteturas. A hipótese de que desligar oneDNN, fixar uma thread e limitar despacho ATen/MKL seria suficiente foi refutada nesse par. Não relaxar a comparação nem publicar v4.

**Próxima investigação econômica:** workflow de diagnóstico independente com um único passo Adam sobre 126 amostras sintéticas; registrar hashes de entrada, pesos iniciais, logits, loss, gradientes e pesos atualizados, identificando a primeira etapa divergente. Esse probe é intencionalmente distinto do treinamento completo v4: se passar, **não** demonstra reprodutibilidade de 22 épocas. O workflow é separado para não repetir o treinamento dos quatro modelos a cada instrumentação.
 
**Correção do probe:** a primeira execução do workflow diagnóstico falhou antes da inferência com `ValueError: Training sample count must be positive and class-balanced` porque 128 não é múltiplo das 7 classes. A amostra foi ajustada para 126 (18 exemplos por classe); não houve evidência numérica da execução falha.


### Contabilização de silêncio e DC — revisão de 10/11/2026

O avaliador offline registra `windows_selected`, `windows_skipped_silence`,
`windows_rejected_preprocessing`, `windows_inferred` e
`pipeline_coverage` (inferidas / selecionadas), além de separação de
rejeições de pré-processamento entre rótulos conhecidos e UNKNOWN.
Os resumos por sessão de cobertura e acurácia não expõem identificadores.
As janelas silenciosas não são inferidas; janelas IQ com DC constante são
rejeitadas pelo pré-processador, sem interromper todo o lote. **Nenhuma
rejeição pré-neural é contada como acerto UNKNOWN da rede.**

Matriz de confusão, recall, acurácia, taxas de aceitação e bootstrap são
**condicionais às janelas efetivamente inferidas**. Quando não houver janelas
inferidas, essas métricas são `null` (ou matriz de zeros), nunca 0%/100%
inventados. Uma sessão sem inferência é contabilizada em
`session_accuracy_summary.sessions_without_inference`; a cobertura
min/max por sessão fica em `session_pipeline_coverage_summary`.
Os relatórios não substituem a inspeção humana de silêncio, CW chaveado,
portadora não modulada e espúrios DC.

A execução [#70](https://github.com/alexpmr/PT2VHF-SDR-Tool/actions/runs/42882889533)
concluiu com **FAILURE** no replay exato entre CPUs AMD EPYC 9V45 e 9V74:
entradas e pesos iniciais idênticos, pesos finais divergentes (diferença
máxima 1.1864783763885498). O job principal aprovou 156 testes IQ e
exportação/paridade ONNX, mas o workflow completo **não** passou.
Este problema é independente da correção do avaliador; a causa numérica
específica ainda precisa ser isolada.

A alteração do avaliador e dos testes offline não dispara mais o treinamento
ONNX pesado: o CI geral de pull request executa `scripts/run_tests.py`.
O treinamento continua disponível por acionamento manual, exclusivamente
quando houver hipótese nova a investigar. **Todos os testes aqui são
sintéticos; não houve homologação RF real.**

### Diagnóstico v4 representativo de quatro passos (instrumentação 10/11/2026)

O probe anterior de um único passo usava 126 amostras sem substituir os
exemplos UNKNOWN da v4. Assim, não reproduzia os minibatches do treinamento
que falhou nas execuções #69/#70. A instrumentação agora usa os mesmos
8.400 exemplos sintéticos, a substituição UNKNOWN de 90%, o conjunto de
validação, os pesos iniciais e a permutação da primeira época da v4.
Registra hashes de índices, lotes, logits, perda, gradientes e pesos após
cada um dos quatro primeiros passos Adam, em dois jobs independentes.

O comparador sinaliza a primeira etapa divergente e separa explicitamente
`SAME_CPU_ONLY_INCONCLUSIVE` de comparação entre CPUs diferentes. Não
relaxa tolerâncias nem executa 22 épocas. Mesmo uma comparação bem-sucedida
não comprova reprodutibilidade do treinamento completo nem validação RF.
Os resultados só serão considerados após conclusão verificável do CI.
