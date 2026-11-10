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

Revisar matriz de confusão, recall por classe (em especial CW/AM), erros de alta confiança, curva de aceitação de UNKNOWN, cobertura de sinais conhecidos, acurácia média por sessão e latência/uso de CPU medidos separadamente. O script atual **não** calcula todos esses indicadores de implantação (por exemplo, latência ou intervalo de confiança): não inferir os ausentes.

## Portões para revisão do PR

- Documentar origem, proveniência e conferência independente de rótulos; validar que o dataset não entrou no treinamento.
- Avaliar classes e OOD por **sessão**, **dispositivo** e **faixa de SNR**; exigir relatório de incerteza e não apenas média por janela altamente correlacionada.
- Sinalizar explicitamente **WFM não validado** no contrato atual: 48 kS/s/2.048 amostras não é evidência para broadcast FM convencional.
- Bloquear decisão automática de VFO/modo até teste operacional supervisionado.
- **Sem gravações RF reais disponíveis, o status da IA permanece EXPERIMENTAL**, mesmo com todos os workflows verdes.

## Intervalo de confiança por sessão (atualização de 10/11/2026)

O script `evaluate_iq_recordings.py` inclui `session_macro_accuracy_ci95`, um intervalo exploratório de 95% por **bootstrap de sessões**, e `session_accuracy_summary` (mínimo, máximo e contagem, sem nomes/IDs de sessão). O cálculo exige **ao menos três sessões** e retorna `null` quando houver menos, evitando apresentar janelas altamente correlacionadas como observações independentes. A sequência aleatória é determinística para auditoria; 2.000 reamostragens por padrão.

**Limitação essencial:** intervalo bootstrap não corrige rótulos errados, viés de seleção, dependência entre sessões, ausência de diversidade de SDR nem prova desempenho operacional. A versão experimental foi submetida ao [Actions #66](https://github.com/alexpmr/PT2VHF-SDR-Tool/actions/runs/42845233390) para testes; verificar o resultado antes de citar a implementação como aprovada.
