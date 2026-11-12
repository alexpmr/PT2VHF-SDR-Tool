# IQ/ONNX — Calibração e holdout separados por sessão

**Ferramenta de pesquisa; nenhuma gravação RF real foi homologada.** O modelo não deve selecionar o modo do receptor automaticamente.

Execute localmente, com os dois manifestos descritos em docs/IQ_RF_EVALUATION.md, separados por sessões independentes:

`python -m scripts.iq_session_gate --calibration-manifest meus_iq/calibracao.json --holdout-manifest meus_iq/holdout.json --root meus_iq --model models/iq/synthetic_v4.onnx --out gate_privado.json --max-unknown-far 0.10 --min-known-coverage 0.50`

O script rejeita sessões presentes em ambos os conjuntos, WAV repetidos por caminho e cópias idênticas por SHA-256. Cada conjunto precisa de sinais conhecidos e UNKNOWN de sessões separadas. Os limiares candidatos são 0,80, 0,90, 0,95, 0,99 e 0,999; **a escolha acontece exclusivamente na calibração**. O holdout só verifica a escolha já congelada.

**Integridade dos rótulos por sessão (11/11/2026):** o gate agora rejeita manifestos em que um mesmo `session_id` contenha simultaneamente gravações rotuladas como sinal conhecido e `UNKNOWN`, mesmo quando o conjunto possui outros IDs de sessão suficientes para passar na contagem anterior. Esse agrupamento misto introduzia pseudorreplicação na estimativa macro por sessão e contrariava a exigência de sessões separadas. Diferentes modos *conhecidos* podem continuar no mesmo ID quando a proveniência justificar, mas a independência RF e os rótulos ainda exigem conferência externa. Dois testes exclusivamente sintéticos cobrem calibração e holdout.

O holdout exige **pelo menos quatro sessões independentes**, sendo **duas de sinais conhecidos e duas UNKNOWN**, com **dois dispositivos SDR distintos em cada população** antes de devolver `HOLDOUT_EVALUATED`. Se os limites empíricos forem satisfeitos, mas faltar diversidade, a decisão será `HOLDOUT_INSUFFICIENT_DIVERSITY` (código de saída 2). `holdout_diversity_gate_passed` registra esse portão separadamente. Os metadados declarados no manifesto **não provam** independência nem origem RF; é necessária conferência humana.

As taxas são apresentadas tanto por janela quanto como média entre sessões. O mecanismo exige um limite empírico de falsa aceitação de UNKNOWN e cobertura mínima de sinais conhecidos; se não houver limiar, devolve NO_ACCEPTABLE_THRESHOLD. Se o holdout falhar, devolve HOLDOUT_FAILED. Não seleciona outro limiar com base no holdout.

HOLDOUT_EVALUATED indica apenas que o limite empírico foi observado. **Não comprova acurácia operacional**, pois as janelas de uma sessão são correlacionadas, os rótulos dependem de verificação externa e as gravações podem não representar equipamentos, interferências e modos reais. A variável operationally_validated é sempre false.

Os arquivos IQ e seus identificadores permanecem locais. Não publicar manifestos privados nem gravações no GitHub.

## Cobertura de inferência e rejeições de pré-processamento (11/11/2026)

A avaliação de calibração e holdout agora registra separadamente `windows_selected`, `windows_skipped_silence`, `windows_rejected_preprocessing`, `windows_inferred`, `pipeline_coverage` e `minimum_session_pipeline_coverage`. As métricas de acurácia/FAR são **condicionais às janelas inferidas**: silêncio e portadoras DC rejeitadas não podem virar acertos UNKNOWN. Os relatórios de cobertura não expõem identificadores de sessões.

O novo limite `--min-pipeline-coverage 0.80` (padrão conservador, **não calibrado em RF real**) exige inferência em pelo menos 80% das janelas selecionadas **em cada sessão**, tanto na calibração quanto no holdout. Mesmo com acurácia/FAR aparentemente favoráveis e diversidade de SDRs suficiente, a decisão passa a `HOLDOUT_INSUFFICIENT_PIPELINE_COVERAGE` (exit 2) se qualquer sessão não cumprir o limite. O valor pode ser ajustado para pesquisa, mas **reduzi-lo não constitui homologação**. Gravação sem nenhuma janela inferível continua falhando explicitamente; erros inesperados do modelo não são mascarados como rejeição DC.

Os totais são amostrais (até `--max-windows` por WAV); a cobertura de janelas não equivale a tempo de transmissão detectado nem substitui revisão de RF real e rótulos independentes. Testes automatizados usam exclusivamente WAV sintético.

## Contrato de probabilidades do gate (11/11/2026)

O gate exige as sete classes esperadas, pontuações finitas em [0, 1] e soma de probabilidades igual a 1 com tolerância absoluta de 0,0001 para arredondamento. Pontuações arbitrárias ou não normalizadas não podem definir limiares de UNKNOWN. O classificador ONNX atual aplica softmax; essa checagem é defesa adicional para artefatos ou stubs incorretos. Os testes são exclusivamente sintéticos e não demonstram desempenho RF.


## Diversidade específica de UNKNOWN no holdout (12/11/2026)

Uma contagem global de três sessões e dois SDRs podia retornar
`HOLDOUT_EVALUATED` mesmo quando **todo UNKNOWN vinha de uma única sessão
e um único equipamento**. Isso torna a taxa de falsa aceitação de UNKNOWN
especialmente frágil, ainda que existam milhares de janelas correlacionadas.

O gate agora exige **pelo menos duas sessões independentes de sinais
conhecidos e duas sessões UNKNOWN**, com **dois SDRs distintos em cada
população**. O relatório apresenta separadamente
`holdout_known_sessions`, `holdout_unknown_sessions`,
`holdout_known_devices` e `holdout_unknown_devices`. Caso contrário,
a decisão é `HOLDOUT_INSUFFICIENT_DIVERSITY` e o comando retorna código 2.
Esses mínimos são **guardas metodológicos de pesquisa**, não metas de
homologação RF. Para homologação, ainda são necessários rótulos verificados
externamente, maior diversidade e análise de incerteza por sessão.

Testes usam apenas WAV sintético e predições simuladas. Nenhuma medição RF
real ou taxa de acerto operacional foi produzida por esta mudança.

## Proteção por classe conhecida — 12/11/2026

A cobertura média de sinais conhecidos, inclusive por sessão e por SDR, pode
ocultar uma classe com recall zero (por exemplo, CW falhando enquanto muitas
sessões AM são corretamente reconhecidas no mesmo equipamento). O gate
experimental agora calcula `known_worst_class_session_macro_coverage`: para
cada classe conhecida **observada**, calcula a fração de acertos aceitos em
cada sessão e depois a média entre sessões; o mínimo entre as classes deve
satisfazer `--min-known-coverage`. O relatório inclui
`known_classes_observed` sem identificadores de sessão ou dispositivo.

**Limite importante:** o mínimo só considera classes presentes no conjunto.
A ausência de CW, AM ou outra classe necessária **não** é prova de desempenho
nessa classe, e `HOLDOUT_EVALUATED` continua sendo apenas um diagnóstico
offline, não uma aprovação para release. A revisão de RF real deve exigir
cobertura explícita de CW/AM/NFM/USB/LSB e UNKNOWN, diversidade de sessões,
SDRs, SNR e verificação independente dos rótulos. WFM permanece não validado.
Os testes desta alteração usam apenas observações sintéticas.


## Gate fail-closed para classes ausentes — 12/11/2026

Um holdout com previsões perfeitas de AM e UNKNOWN, mas **sem CW, NFM, USB
ou LSB**, não pode retornar `HOLDOUT_EVALUATED` como se todas as classes
conhecidas tivessem sido examinadas. O gate agora exige **CW, AM, NFM,
USB e LSB em ambos os manifestos** (calibração e holdout). A ausência de
qualquer uma retorna `HOLDOUT_INSUFFICIENT_CLASS_COVERAGE` (exit 2)
quando os demais limites forem satisfeitos. O relatório expõe apenas nomes
de modos ausentes e `holdout_class_coverage_gate_passed`, sem IDs privados.

**WFM permanece fora do contrato de RF a 48 kS/s**, não entra no conjunto
obrigatório. Presença de rótulo não prova sua veracidade, nem garante
recall, independência entre sessões ou qualidade RF; o gate continua offline,
`operationally_validated=false`. Os testes desta alteração usam WAVs
sintéticos e predições simuladas. Não é homologação nem autorização de merge.


## Cobertura cruzada classe × SDR — 12/11/2026

A média de cobertura por classe e a média por SDR, verificadas
**separadamente**, podem passar enquanto uma combinação específica
falha completamente: por exemplo, CW em um segundo SDR com recall zero,
mas CW funcionando no primeiro SDR e AM funcionando em ambos.

O gate agora calcula
`known_worst_class_device_correct_coverage` sobre cada célula
**observada** (classe conhecida × dispositivo SDR) e exige o mesmo
`--min-known-coverage` para a pior célula. O campo
`known_class_device_cells_observed` informa quantas combinações foram
medidas, sem divulgar identificadores de sessões ou dispositivos.
O diagnóstico e a seleção de limiar continuam separados por sessão
(calibração versus holdout).

**Limitações:** uma célula com uma única janela pode produzir 0% ou 100%
sem precisão estatística; as janelas não são independentes. Combinações
classe × SDR **ausentes** não são testadas pelo mínimo, e a diversidade
global de dois SDRs não garante que todos os modos tenham sido observados
em ambos. Para homologação RF, exigir matriz completa por classe/SDR,
sessões independentes, distribuição de SNR e intervalos de incerteza
por sessão. Nenhum teste sintético prova acurácia RF ou autoriza promoção.


## Pior sessão UNKNOWN e pior célula classe × SDR × sessão — 12/11/2026

**Nova hipótese de mascaramento testada apenas com observações sintéticas:**
a taxa de falsa aceitação de UNKNOWN pode ser baixa globalmente, na média
entre sessões e até por SDR, mas chegar a 100% em uma única sessão ruim.
Analogamente, CW pode falhar totalmente em uma sessão de um SDR, enquanto
outras sessões com muitas janelas corretas fazem a cobertura da mesma
classe × SDR parecer adequada. Janelas correlacionadas não substituem
sessões independentes.

O gate de pesquisa agora exige também:
- `unknown_worst_session_false_accept_rate <= --max-unknown-far`;
- `known_worst_class_device_session_correct_coverage >= --min-known-coverage`
  quando há identidade de SDR, como é obrigatório na avaliação fim a fim.

O relatório inclui o número de células observadas
`known_class_device_session_cells_observed`, mas **não** divulga IDs de
sessões ou nomes de dispositivos. A seleção de limiar continua restrita à
calibração; o holdout usa o limiar congelado. Os novos mínimos não substituem
contagens amostrais, intervalos de confiança, diversidade de famílias OOD,
SNR, rótulos externos ou captura RF genuína. Um único resultado de sessão
pode ser estatisticamente instável: o critério é conservador e exploratório,
não uma estimativa validada de risco operacional.

Três testes sintéticos cobrem falsa aprovação OOD em sessão isolada,
falha CW em uma célula classe × SDR × sessão e controle positivo/compatibilidade
com a API unitária legada. **Nenhuma validação RF real foi executada.**
