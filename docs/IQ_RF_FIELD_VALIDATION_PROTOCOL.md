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
4. Planejar a coleta por **split, SDR, modo e sessão**, com **pelo menos dois SDRs físicos distintos no holdout**. O gate atual exige **duas sessões distintas para cada combinação de SDR × CW/AM/NFM/USB/LSB/UNKNOWN no holdout**, além de pelo menos duas sessões conhecidas e duas UNKNOWN e de todas as classes conhecidas globalmente na calibração. Sessões de modos conhecidos podem compartilhar um ID somente quando a proveniência justificar; UNKNOWN deve ficar em sessões separadas. Os IDs do holdout não podem aparecer na calibração. **Três sessões no total não satisfazem o gate atual**; nenhum desses mínimos garante poder estatístico ou autenticidade RF.
5. Dividir treino, ajustes de limiar e avaliação **por sessão e dispositivo**, evitando que segmentos da mesma transmissão apareçam em conjuntos diferentes. Nunca treinar em dados reservados para avaliação cega.
6. Guardar os WAVs RF brutos e o manifesto **fora do GitHub**; não incluir identificadores pessoais nem conteúdo de comunicações particulares nos relatórios públicos. Confirmar licitude/consentimento quando necessário.

## QA de portadora contínua OOD — revisão de 13/11/2026

Uma portadora **não modulada** e comprovadamente fora das classes é um controle
negativo indispensável para testar falsa aceitação como CW/AM. A auditoria
`audit_iq_dataset.py` anteriormente classificava qualquer IQ quase constante
rotulado `UNKNOWN` como `BLOCK`, removendo justamente esse controle do
corpus antes da avaliação. Agora, uma gravação não silenciosa e não saturada
com IQ quase constante recebe
`REVIEW: constant_unknown_carrier_or_hardware_dc` e exige verificação externa
da origem RF, offset e ausência de espúrio DC. Não é `PASS` automático.
Silêncio, clipping excessivo, cópia exata entre sessões e IQ constante
rotulado NFM/USB/LSB continuam bloqueantes conforme as demais regras.

**Separação de métricas:** o pré-processamento ONNX pode rejeitar um IQ
puramente constante como `No usable RF signal`. Isso deve aparecer como
exclusão pré-inferência, **nunca** como acerto neural UNKNOWN nem como prova
de rejeição OOD. Para testar a rejeição neural de portadoras, também coletar
portadoras reais deslocadas do centro, com amplitude/frequência verificadas
independentemente e janelas inferíveis. Os testes desta política usam PCM
sintético e não constituem homologação RF.

## Limite temporal fundamental: CW versus portadora OOD (revisão de 12/11/2026)

O classificador ONNX recebe **2.048 amostras complexas a 48.000 amostras/s**:
cada decisão observa apenas **42,67 ms** de IQ. Isso é um limite do contrato
atual, não uma medição de RF. Pela convenção de velocidade CW, a duração de um
ponto é `1,2 / WPM` segundos: **60 ms a 20 WPM** e **40 ms a 30 WPM**.
Portanto, mesmo um CW perfeitamente rotulado pode produzir janelas inteiras
contendo apenas portadora ligada, sem qualquer transição de chaveamento.

**Consequência de identificabilidade:** uma janela de CW sem transições e uma
portadora contínua não modulada, com frequência/amplitude/ruído equivalentes,
podem ser indistinguíveis nesse intervalo. Não existe limiar de confiança
softmax capaz de resolver, sozinho, uma ausência de informação física. Não
tratar uma portadora contínua reconhecida como CW como acerto. Uma eventual
política de abstinência/UNKNOWN precisa de evidência temporal de chaveamento
(ou de uma fonte externa), preservando explicitamente o estado **indeterminado**
quando a observação é curta demais. Isso requer desenho e QA próprios, não
apenas aumentar o limiar ou treinar novas sementes sintéticas.

**Requisito adicional para o corpus RF:** registrar segmentos CW completos
contendo vários pontos/traços e silêncios, com timestamps e rótulos
independentes; avaliar tanto janelas de 42,67 ms quanto sequências
multijanela e estratificar por velocidade CW. Capturar portadoras OOD
contínuas, também com verificação externa, no mesmo plano de SNR/deslocamento
de frequência. A divisão treino/calibração/holdout continua por sessão e
dispositivo; janelas adjacentes da mesma transmissão não são independentes.
Esse protocolo não constitui validação executada nem autoriza classificação
automática de modo.

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

### Integridade de tipos no manifesto (13/11/2026)

O avaliador offline rejeita `session_id`, `device` e `path` que não
sejam strings não vazias, e exige `frequency_hz` numérico finito e
estritamente positivo (não aceita texto numérico nem booleanos). Sem esse
controle, valores como `session_id: 123` e `device: true` seriam
convertidos silenciosamente em texto, aparentando identidades de sessão ou
equipamento válidas e contaminando verificações de diversidade do corpus.
Onze testes **sintéticos de esquema** cobrem essas rejeições.

**Limitação:** identificadores bem formados não comprovam sessões
independentes, SDRs físicos distintos, frequências verdadeiras ou rótulos RF.
A conferência externa do manifesto e das gravações permanece obrigatória.

### Integridade tipada do sidecar bruto (13/11/2026)

A preparação de capturas verifica também o **tipo** dos metadados do
sidecar `.iq.json` (esquemas 1 e 2): versão inteira explícita,
`center_hz` numérico finito e positivo (não booleano),
`sample_rate_hz` e `written_frames` inteiros, quatro contadores de
continuidade inteiros iguais a zero, e `invalid_reasons` como lista vazia.
Um `false` não pode substituir o contador `0`, e `{}`, `""` ou
`null` não podem substituir `[]`. A verificação de SHA-256 do esquema
2 permanece obrigatória e separada. **24 casos sintéticos** de regressão
cobrem esses metadados nos dois esquemas.

Isso impede que um manifesto aparentemente íntegro derive de um sidecar
com tipos incompatíveis e contadores de continuidade ambíguos; **não
autentica hardware, origem RF, sessões, rótulos ou medições de desempenho**.
A validação externa de capturas reais permanece obrigatória.

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
- A auditoria compara hashes de WAVs completos e amostras de janelas IQ **nas bordas, nos quartos e no meio** das gravações para detectar reutilização exata entre calibração e holdout. Essa amostragem limitada não identifica todas as cópias modificadas, deslocadas, reamostradas ou vazamentos fora das posições inspecionadas; a proveniência e os rótulos continuam exigindo verificação independente.

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

O parâmetro `--max-windows` seleciona até 100 janelas IQ **não sobrepostas e uniformemente distribuídas ao longo de cada WAV** (incluindo início e fim quando há ao menos duas janelas; com limite 1, seleciona a janela central), em vez de considerar apenas os primeiros segundos. Isso reduz o viés temporal de início de gravação, mas continua sendo uma amostragem determinística limitada; transmissões curtas entre janelas podem não ser observadas. Para ensaios de sensibilidade temporal, aumentar o limite e documentar a cobertura.

Revisar matriz de confusão, recall por classe (em especial CW/AM), erros de alta confiança, curva de aceitação de UNKNOWN, cobertura de sinais conhecidos, acurácia média por sessão e latência/uso de CPU medidos separadamente. O script calcula um intervalo exploratório de confiança por bootstrap de sessões (descrito abaixo), mas **não** calcula latência nem uso de CPU operacional: medir esses indicadores separadamente. A matriz de confusão e o recall utilizam a decisão efetiva do classificador, inclusive o limiar configurado para UNKNOWN; a curva de aceitação aplica cada limiar de forma independente sobre as probabilidades brutas. Não confundir as duas políticas.

## Gate adicional por SDR — revisão de 12/11/2026

A taxa de falsa aceitação UNKNOWN agregada e a média por sessão podem ocultar
falha concentrada em um SDR quando outro dispositivo contribui muitas sessões.
O avaliador de limiar experimental passa a registrar, **sem nomes de dispositivos
no JSON público**, a maior taxa de falsa aceitação UNKNOWN por SDR e a menor
cobertura correta de sinais conhecidos por SDR. Para aprovar o limiar, esses
piores casos também precisam satisfazer os limites configurados, além das
métricas globais e por sessão. O gate fim a fim exige identidade de SDR
associada a cada observação; quatro campos sem dispositivo continuam aceitos
somente nas funções unitárias legadas de cálculo.

**Importante:** essas taxas são descritivas, não limites superiores de confiança.
Duas sessões com poucas janelas por SDR podem ser insuficientes para estimar
o risco; nomes de SDR fornecidos pelo manifesto não demonstram hardware
independente. A auditoria deve confirmar dispositivos físicos e sessões
externamente, estratificar por SNR e família OOD, e reportar contagens por
dispositivo sem expor IDs pessoais. Nenhuma execução sintética é homologação RF.

## Cobertura cruzada de modos por SDR no holdout (12/11/2026)

Além de exigir CW/AM/NFM/USB/LSB no conjunto global, o gate offline
agora exige **cada uma dessas cinco classes e UNKNOWN em cada SDR declarado
no holdout**. A ausência de uma combinação modo × SDR reprova com
`HOLDOUT_INSUFFICIENT_CLASS_DEVICE_COVERAGE`, mesmo quando as médias de
acerto e as taxas de rejeição observadas são perfeitas. O JSON expõe somente
o número de combinações esperadas e ausentes, sem nomes dos equipamentos.
A calibração continua exigindo todas as classes globalmente; a cobertura
cruzada é requisito específico do holdout independente.

**Replicação exigida no holdout:** cada célula SDR × modo (incluindo UNKNOWN)
precisa conter **ao menos duas sessões distintas**, sob o bloqueio
`HOLDOUT_INSUFFICIENT_CLASS_DEVICE_SESSION_DIVERSITY`. Janelas adicionais
na mesma sessão não substituem replicação. A calibração exige todas as cinco
classes conhecidas globalmente, mas não essa matriz cruzada de replicação.

**Limites:** presença e replicação mínima não significam representatividade
estatística. A rejeição OOD é também avaliada pela pior combinação SDR × sessão,
sem expor os identificadores no relatório. As identidades dos SDRs, a
independência das sessões, os rótulos e a origem RF precisam ser auditados
externamente. Os testes dessa política são sintéticos, não homologação RF.

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

### Segunda etapa do probe: localizar a primeira camada (10/11/2026)

A [execução #3](https://github.com/alexpmr/PT2VHF-SDR-Tool/actions/runs/42917860408)
comparou Intel Xeon Platinum 8573C e AMD EPYC 7763. Entradas, pesos iniciais,
permutação e primeiro lote idênticos; a **primeira diferença foi no forward
da primeira minibatch**, antes do backward/Adam. O hash da perda do primeiro
passo coincidiu, mas gradientes e pesos divergiram. Não atribuir a causa
exclusivamente ao otimizador. O diagnóstico seguinte registra a saída de
cada camada Conv1d/ReLU/AdaptiveAvgPool/Linear sem alterar a arquitetura,
para isolar o primeiro operador divergente. A instrumentação é sintética e
não constitui homologação de RF real.


### Probe escalar da primeira Conv1d — 10/11/2026

Reanálise dos logs históricos, sem treinamento: no
[probe #3](https://github.com/alexpmr/PT2VHF-SDR-Tool/actions/runs/42917860408),
Intel Xeon Platinum 8573C divergiu de AMD EPYC 7763 no primeiro forward.
Os hashes dos quatro passos AMD EPYC 7763 (#3) e AMD EPYC 9V74
([probe #4](https://github.com/alexpmr/PT2VHF-SDR-Tool/actions/runs/42918360685))
foram idênticos, incluindo logits, gradientes e pesos, com os mesmos
dados, pesos iniciais, versão PyTorch e política de CPU. O #4, sozinho,
comparou duas CPUs 9V74 e não validou heterogeneidade.

A hipótese é diferença numérica dependente do backend Intel/AMD;
a primeira camada responsável ainda não foi comprovada, pois o
probe Intel #3 não continha hashes por camada. O novo diagnóstico
compara 32 amostras da primeira Conv1d a uma referência escalar
float64 e mede erros absolutos entre runners. A referência é
**somente diagnóstica**: não muda treinamento, pesos, arquitetura
ou o runtime do SDR. Os hashes exatos por camada continuam
obrigatórios; amostras esparsas não provam equivalência do tensor
completo nem reprodutibilidade de 22 épocas. Testes exclusivamente
sintéticos, sem homologação RF.


### Primeira camada divergente localizada — probe #6 (10/11/2026)

A [execução #6](https://github.com/alexpmr/PT2VHF-SDR-Tool/actions/runs/42924675133)
comparou AMD EPYC 9V45 com AMD EPYC 9V74. As saídas da
**primeira Conv1d e ReLU foram idênticas**; a primeira divergência
SHA-256 ocorreu em **`steps[0].layers.02_Conv1d`**, isto é,
a segunda convolução, antes do backward/Adam. As 32 amostras da
primeira Conv1d coincidiram exatamente e tiveram erro máximo
de 1,4948656712476804e-7 frente à referência escalar float64.
Isso localiza a primeira divergência nesse par de CPUs, mas
não prova qual instrução ou backend a provoca. O job falhou
deliberadamente com código 2; não é uma falha de empacotamento.

O probe seguinte mede também 32 saídas da segunda Conv1d contra
referência escalar, sem alterar o modelo nem executar 22 épocas.
A medição é **esparsa**, e os hashes integrais continuam sendo
o critério de identidade; os resultados não homologam RF.


### Comparabilidade por janela entre modelos (11/11/2026)

A comparação entre v2–v5 exige inferência **nas mesmas janelas IQ de cada
gravação**, não apenas contagens agregadas iguais. Dois modelos podem rejeitar
janelas distintas no pré-processamento e ainda exibir totais idênticos,
invalidando uma comparação direta de acurácia. O avaliador verifica os pares
(índice da gravação, índice da janela) em memória e interrompe a comparação
se os conjuntos diferirem. Os índices não aparecem no relatório público.
Investigar modelos individualmente quando a comparabilidade falhar.
Testes exclusivamente sintéticos; nenhuma homologação RF real.


### Integridade das observações agregadas de limiar (13/11/2026)

O cálculo experimental de cobertura e falsa aceitação em
`scripts/iq_session_gate.py::rates` agora valida diretamente as observações
recebidas, inclusive quando a função é chamada fora do fluxo completo de
inferência. Confianças `NaN`, infinitas, negativas, maiores que 1,
booleanas ou textuais, limiares inválidos, classes de referência fora do
contrato (inclusive WFM) e identificadores de sessão/dispositivo inválidos
causam erro explícito. Valores reais NumPy continuam aceitos.

**Motivo:** uma confiança `NaN` em uma amostra `UNKNOWN` anteriormente
tornava falsa a comparação `confidence >= threshold`, podendo reduzir
artificialmente a taxa de falsa aceitação OOD. Os testes adicionados são
sintéticos e verificam apenas integridade de cálculo; não constituem
medição RF, validação de rejeição neural ou autorização de publicação.


### Integridade dos limites de decisão RF/OOD (13/11/2026)

Os parâmetros `max_far`, `min_coverage` e `min_pipeline_coverage` devem ser
números reais finitos entre 0 e 1. Valores booleanos, strings numéricas,
`null`, NaN, infinito e números fora do intervalo são rejeitados. Em Python,
`True == 1` e `False == 0`: aceitar `max_far=True` poderia permitir
100% de falsa aceitação UNKNOWN, enquanto `min_coverage=False` ou
`min_pipeline_coverage=False` poderia desativar silenciosamente a cobertura
mínima. A mudança é proteção de esquema, coberta por testes sintéticos; não
representa medição de RF nem aprovação da IA.


### Integridade dos hashes do comparador AMD × Intel (13/11/2026)

O comparador de diagnósticos sintéticos `compare_iq_cpu_step.py` exige agora
SHA-256 hexadecimal minúsculo de 64 caracteres para os campos globais, cada
etapa do otimizador e os hashes das camadas. Dois relatórios igualmente
malformados não podem mais ser interpretados como concordância numérica.
A alteração é coberta por testes com testemunhos artificiais; **não** constitui
reprodução em processadores AMD e Intel físicos, nem homologação de RF.
