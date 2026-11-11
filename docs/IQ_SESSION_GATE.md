# IQ/ONNX — Calibração e holdout separados por sessão

**Ferramenta de pesquisa; nenhuma gravação RF real foi homologada.** O modelo não deve selecionar o modo do receptor automaticamente.

Execute localmente, com os dois manifestos descritos em docs/IQ_RF_EVALUATION.md, separados por sessões independentes:

`python -m scripts.iq_session_gate --calibration-manifest meus_iq/calibracao.json --holdout-manifest meus_iq/holdout.json --root meus_iq --model models/iq/synthetic_v4.onnx --out gate_privado.json --max-unknown-far 0.10 --min-known-coverage 0.50`

O script rejeita sessões presentes em ambos os conjuntos, WAV repetidos por caminho e cópias idênticas por SHA-256. Cada conjunto precisa de sinais conhecidos e UNKNOWN de sessões separadas. Os limiares candidatos são 0,80, 0,90, 0,95, 0,99 e 0,999; **a escolha acontece exclusivamente na calibração**. O holdout só verifica a escolha já congelada.

**Integridade dos rótulos por sessão (11/11/2026):** o gate agora rejeita manifestos em que um mesmo `session_id` contenha simultaneamente gravações rotuladas como sinal conhecido e `UNKNOWN`, mesmo quando o conjunto possui outros IDs de sessão suficientes para passar na contagem anterior. Esse agrupamento misto introduzia pseudorreplicação na estimativa macro por sessão e contrariava a exigência de sessões separadas. Diferentes modos *conhecidos* podem continuar no mesmo ID quando a proveniência justificar, mas a independência RF e os rótulos ainda exigem conferência externa. Dois testes exclusivamente sintéticos cobrem calibração e holdout.

O holdout exige **pelo menos três sessões independentes e dois dispositivos SDR distintos** antes de devolver `HOLDOUT_EVALUATED`. Se os limites empíricos forem satisfeitos, mas faltar diversidade, a decisão será `HOLDOUT_INSUFFICIENT_DIVERSITY` (código de saída 2). `holdout_diversity_gate_passed` registra esse portão separadamente. Os metadados declarados no manifesto **não provam** independência nem origem RF; é necessária conferência humana.

As taxas são apresentadas tanto por janela quanto como média entre sessões. O mecanismo exige um limite empírico de falsa aceitação de UNKNOWN e cobertura mínima de sinais conhecidos; se não houver limiar, devolve NO_ACCEPTABLE_THRESHOLD. Se o holdout falhar, devolve HOLDOUT_FAILED. Não seleciona outro limiar com base no holdout.

HOLDOUT_EVALUATED indica apenas que o limite empírico foi observado. **Não comprova acurácia operacional**, pois as janelas de uma sessão são correlacionadas, os rótulos dependem de verificação externa e as gravações podem não representar equipamentos, interferências e modos reais. A variável operationally_validated é sempre false.

Os arquivos IQ e seus identificadores permanecem locais. Não publicar manifestos privados nem gravações no GitHub.

## Cobertura de inferência e rejeições de pré-processamento (11/11/2026)

A avaliação de calibração e holdout agora registra separadamente `windows_selected`, `windows_skipped_silence`, `windows_rejected_preprocessing`, `windows_inferred`, `pipeline_coverage` e `minimum_session_pipeline_coverage`. As métricas de acurácia/FAR são **condicionais às janelas inferidas**: silêncio e portadoras DC rejeitadas não podem virar acertos UNKNOWN. Os relatórios de cobertura não expõem identificadores de sessões.

O novo limite `--min-pipeline-coverage 0.80` (padrão conservador, **não calibrado em RF real**) exige inferência em pelo menos 80% das janelas selecionadas **em cada sessão**, tanto na calibração quanto no holdout. Mesmo com acurácia/FAR aparentemente favoráveis e diversidade de SDRs suficiente, a decisão passa a `HOLDOUT_INSUFFICIENT_PIPELINE_COVERAGE` (exit 2) se qualquer sessão não cumprir o limite. O valor pode ser ajustado para pesquisa, mas **reduzi-lo não constitui homologação**. Gravação sem nenhuma janela inferível continua falhando explicitamente; erros inesperados do modelo não são mascarados como rejeição DC.

Os totais são amostrais (até `--max-windows` por WAV); a cobertura de janelas não equivale a tempo de transmissão detectado nem substitui revisão de RF real e rótulos independentes. Testes automatizados usam exclusivamente WAV sintético.

## Contrato de probabilidades do gate (11/11/2026)

O gate exige as sete classes esperadas, pontuações finitas em [0, 1] e soma de probabilidades igual a 1 com tolerância absoluta de 0,0001 para arredondamento. Pontuações arbitrárias ou não normalizadas não podem definir limiares de UNKNOWN. O classificador ONNX atual aplica softmax; essa checagem é defesa adicional para artefatos ou stubs incorretos. Os testes são exclusivamente sintéticos e não demonstram desempenho RF.
