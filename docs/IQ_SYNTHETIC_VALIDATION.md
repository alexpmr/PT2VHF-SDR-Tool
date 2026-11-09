# Validação experimental IQ → ONNX — 09/11/2026

**Estado:** somente branch `feature/iq-signal-classifier`, PR #2 em rascunho. Não foi integrado à `main` nem publicado em instaladores. **Nenhuma acurácia com RF real foi medida.**

## Conclusão dos candidatos v4/v5 e preparação de RF real — 09/11/2026

- [Treinamento v4 e avaliação dos três primeiros candidatos](https://github.com/alexpmr/PT2VHF-SDR-Tool/actions/runs/42691075377): 40 testes IQ aprovados; v4 treinado com aproximadamente 90% dos exemplos UNKNOWN substituídos por famílias negativas sintéticas independentes; artefato ZIP ID `13706388890`.
- [Comparação dos quatro modelos](https://github.com/alexpmr/PT2VHF-SDR-Tool/actions/runs/42691788442): CI aprovado, 40 testes IQ, 4 exportações ONNX validadas (opset 18); artefato ZIP ID `13707158122`, SHA-256 `91d3c7e7558849783a3fe2591d208bddd0e970aac5dafb7594205493869b82f5`. V5 usa **45%** de exemplos UNKNOWN substituídos, contra 90% no v4; todos avaliados sobre os mesmos 960 exemplos rotulados e 320 negativos por modelo.

| Métrica sintética externa (mesmo workflow) | v3 | v4 | v5 |
| --- | ---: | ---: | ---: |
| Acurácia geral top-1 | 70,0% | **77,2%** | 69,5% |
| Recall UNKNOWN (média sobre SNR 0/6/12/20 dB) | 0% | **100%** | 60% |
| Erros de classificação com confiança ≥80% | 24,7% | **15,2%** | 19,3% |
| Falsa aceitação OOD com confiança ≥80% | 86,3% | 20,3% | **18,4%** |
| Sinais conhecidos corretamente aceitos com confiança ≥80% | **78,2%** | 61,4% | 66,5% |
| Erro de calibração ECE | 0,248 | **0,157** | 0,207 |

O v4 reduz falso positivo e recupera UNKNOWN, mas tem recall de CW entre **12,5% e 20%** (dependendo de SNR); o v5 não resolve o problema. A falsa aceitação de portadora contínua no v4 ainda é ~78,7%. **Nenhum modelo deve ser integrado à sintonia automática nem promovido para produção.** Treinar e ajustar continuamente na mesma bateria sintética cria risco de sobreajuste por seleção de hiperparâmetros; reservar conjunto RF independente e sessões cegas.

- **Preparado o próximo gate:** [protocolo para gravações reais](IQ_RF_EVALUATION.md) e `scripts/evaluate_iq_recordings.py` com WAV IQ estéreo PCM16/48 kS/s centrado e metadados rotulados por sessão. O relatório contém matriz de confusão e média por sessão, sem nomes/indicativos no JSON. O caminho de arquivos é restrito à pasta de gravações.
- [CI da ferramenta WAV](https://github.com/alexpmr/PT2VHF-SDR-Tool/actions/runs/42693172356): **163 testes Linux/Qt aprovados**, incluindo leitor e agregação com WAV sintetizados. **Nenhuma captura de antena/SDR foi utilizada nesse CI.**
- **Critério de passagem a campo:** gravações com rótulo verificado externamente, múltiplas sessões e SDRs, SNR variado, sinais vazios e testes de detecção de desconhecidos; WFM requer contrato de taxa de amostragem diferente. Não transportar o relatório sintético para uma alegação de acurácia em RF.

## Avaliação independente do gerador e confiança OOD (09/11/2026)

**Achado de bloqueio para implantação:** os modelos têm generalização insuficiente para sinais sintéticos gerados fora da família de treino. A medida nominal anterior (v3 97,50%) cai para **70,0%** em um conjunto de teste diferente, sem nenhuma captura SDR real. Não extrapolar a taxa para a operação no ar.

- Código de geração independente: `scripts/iq_out_of_family.py`; avaliador `scripts/evaluate_iq_ood.py`; unitários `tests/test_iq_ood_signals.py`.
- Amostras por modelo: **960 rotuladas** (CW, AM, NFM, USB, LSB e UNKNOWN; SNR 0/6/12/20 dB, 40 por classe/nível) e **320 sinais sem classe conhecida** (portadora contínua, chirp, múltiplas portadoras e ruído impulsivo).
- **WFM intencionalmente excluído:** 48 kS/s / 2.048 IQ não permite avaliar corretamente o espectro ocupado de FM comercial. Exige novo contrato de taxa de amostragem/modelagem ou extração de atributos apropriada.
- **Acurácia top-1:** v2 **67,6%**; v3 **70,0%**. Erros de alta confiança (probabilidade máxima ≥0,80) em 24,0% (v2) e 24,7% (v3) das amostras rotuladas. ECE de 10 bins 0,257 (v2) / 0,248 (v3).
- **Ponto crítico:** no conjunto de ruído colorido rotulado UNKNOWN, o v3 teve recall **0%** em todos os níveis de SNR; o v2 também caiu para 0% a partir de 6 dB.
- **Alarmes falsos v3 em sinais sem classe conhecida com limiar 0,80:** portadora contínua 88,7%; chirp 62,5%; múltiplas portadoras 93,8%; ruído impulsivo **100%**.

| Limiar de confiança v3 | Conhecidos corretamente aceitos | Ruído UNKNOWN incorretamente aceito | Sinais fora das classes incorretamente aceitos |
| --- | ---: | ---: | ---: |
| 0,80 | 78,2% | 100,0% | 86,3% |
| 0,90 | 74,5% | 100,0% | 79,7% |
| 0,95 | 70,5% | 99,4% | 75,0% |
| 0,99 | 61,6% | 82,5% | 65,0% |
| 0,999 | 52,1% | 17,5% | 54,1% |

**Interpretação:** aumentar o limiar de softmax sozinho **não separa classes conhecidas de sinais desconhecidos**; mesmo a 99,9%, 54,1% das amostras OOD são incorretamente aceitas, enquanto apenas 52,1% dos sinais válidos são aceitos corretamente. São métricas específicas de sinais sintéticos, não uma estimativa de RF real.

**Orientação para o próximo experimento:** treinar uma classe UNKNOWN com diversidade muito maior e dados independentes, medir *false accept rate* sob distribuição deslocada, calibrar decisões separadamente da classe, usar detecção de ocupação/qualidade do canal e testar validação por sessão/equipamento em gravações IQ verdadeiras. **Não ativar seleção automática de modo no receptor.** 

Evidências: <https://github.com/alexpmr/PT2VHF-SDR-Tool/actions/runs/42668781926> (execução OOD aprovada, relatório e modelo), análise inicial de limiares em <https://github.com/alexpmr/PT2VHF-SDR-Tool/actions/runs/42669412249> (resultados medidos, mas CI reprovado por import do teste, posteriormente corrigido).

## Resultado adicional: treinamento robusto v3 (09/11/2026)

- **Modelo candidato v3:** mesma arquitetura e mesmas sete classes do v2; 8.400 exemplos de treinamento, com 80% de probabilidade de augmentations aleatórias (ganho/fase, frequência ±380 Hz, desequilíbrio I/Q, DC e ruído adicional). Treinamento determinístico com 22 épocas.
- **Validação sem degradação adicional:** 98,00% no conjunto comparável à v2 (seed 991) e 98,57% em segundo conjunto da mesma família geradora (seed 18739). Estes valores **não** são aferições com rádio real.
- **Comparação justa:** o mesmo benchmark sintético com seis cenários e 560 exemplos por cenário foi aplicado a ambos os arquivos ONNX; arquitetura, rótulos, sementes e condições mantidos idênticos.

| Condição | v2 top-1 | v3 top-1 | Δ pontos percentuais | v3 decisão ≥0,80 |
| --- | ---: | ---: | ---: | ---: |
| Nominal | 98,75% | 97,50% | −1,25 | 95,4% |
| Ganho/fase | 98,04% | 97,86% | −0,18 | 96,4% |
| Offset DC | 98,75% | 97,50% | −1,25 | 95,4% |
| Desequilíbrio I/Q | 97,68% | 97,50% | −0,18 | 95,9% |
| CFO +350 Hz | 93,57% | 95,36% | +1,79 | 92,5% |
| Ruído extra −5 dB | 69,29% | **81,61%** | **+12,32** | 70,7% |

- **Ganho real do teste:** resistência ao ruído intenso aumentou **12,32 pontos percentuais**, com perda nominal de 1,25 ponto. O modelo v3 é apenas **candidato experimental preferido no cenário sintético**; não está validado para RF real e não substitui o v2 automaticamente.
- **Exportação:** ONNX opset 18, 31 verificações de paridade PyTorch/ONNX, erro absoluto máximo `1,526 × 10⁻⁵` para v3; 21 testes específicos de IQ passaram. CI Linux/Qt também aprovado na revisão testada.
- **Artefato:** [workflow experimental v3](https://github.com/alexpmr/PT2VHF-SDR-Tool/actions/runs/42666998020), artefato `pt2vhf-iq-synthetic-onnx-experimental` (ID `13696702534`, ZIP SHA-256 `8926a761ed48670c7a0fae0f29c011b5e9d66a63e974e37c1b132d5170f7a87f`), inclui **ambos os modelos**, métricas e comparação. [Suíte geral](https://github.com/alexpmr/PT2VHF-SDR-Tool/actions/runs/42666998240) aprovada.
- **Risco experimental:** o sinal WFM sintético em 48 kS/s não representa adequadamente uma transmissão FM comercial de faixa larga; CW sintetizado com portadora deslocada também pode divergir de IQ real centrado. A alta acurácia pode ser específica do gerador. **Não fazer merge nem publicar como recurso de produção.**
- **Próximo gate:** obter gravações I/Q reais etiquetadas, preferencialmente WAV I/Q estéreo PCM 16-bit, com frequência central, sample rate, modo, modelo do SDR, ganho e informações de recepção. Usar diferentes equipamentos/sessões, exemplos sem sinal e SNR variados; nunca tratar janelas do mesmo arquivo como sessões independentes. Não incluir dados privados sem consentimento.

## Evidência reproduzível

- GitHub Actions: [Experimental IQ model training and ONNX export](https://github.com/alexpmr/PT2VHF-SDR-Tool/actions/runs/42665370841), SHA `cef788e62711947ded1bfbb16281843b1a74a198`; job aprovado.
- Artefato: `pt2vhf-iq-synthetic-onnx-experimental` (ID `13696436287`, ZIP SHA-256 `ab278915da2f29c093cf41212794d21458c4baa933931211afec097d3d5aada1`). Contém `synthetic_v2.onnx`, `.pt`, métricas sintéticas, relatório de estresse e `SHA256SUMS`.
- Treinamento: 5.600 sinais sintéticos, validação independente do mesmo gerador com 1.400 sinais, sete classes (`CW AM NFM WFM USB LSB UNKNOWN`).
- **ONNX opset 18:** validação de assinatura de entrada `float32 [1,2,2048]` e saída `[1,7]`, 31 comparações PyTorch↔ONNX; erro máximo dos logits `7,63 × 10⁻⁶`.
- **16 testes específicos aprovados:** pré-processamento, rejeição de dados inválidos, softmax/limiar, worker, resampling e caminhos negativos.

## Bateria de robustez sintética

Cada cenário usa 560 sinais balanceados (80 por classe), mesma base, seed independente do treinamento, e roda o ONNX Runtime CPU. Acurácia top-1 inclui decisões com baixa confiança; a métrica de decisão com limiar 0,80 é separada.

| Cenário | Top-1 | Decisão (limiar 0,80) | Rejeições de baixa confiança |
| --- | ---: | ---: | ---: |
| Sem perturbação adicional | 98,8% | 97,1% | 10/560 |
| Ganho e rotação de fase | 98,0% | 96,6% | 12/560 |
| Deslocamento DC | 98,8% | 97,1% | 10/560 |
| Desequilíbrio I/Q | 97,7% | 96,6% | 8/560 |
| Desvio de frequência +350 Hz | 93,6% | 92,5% | 11/560 |
| Ruído extra equivalente a −5 dB SNR | 69,3% | 59,3% | 89/560 |

P95 do tempo de processamento do exemplo no runner: ~0,07–0,08 ms; não inclui todo o pipeline SDR (sintonização, resampling, filas, áudio/UI) e não é promessa de latência em um computador de operador. **3360 inferências** de estresse realizadas. O arquivo `synthetic_v2_stress_metrics.json` contém matriz de confusão e recall por classe para cada cenário.

## Limitações e próximos testes obrigatórios

1. Os sinais de treino e teste vêm **do mesmo gerador**: o resultado nominal alto é uma medida de interpolação dentro da distribuição sintética, não de generalização para antenas, canais e modulações reais. O gerador WFM usa desvios elevados em 48 kS/s; esta representação pode ter aliasing e não equivale à banda-base de FM comercial.
2. Os novos testes expuseram sensibilidade a ruído forte e, em menor grau, a offset de frequência. Antes de promover, testar augmentations de SNR, offset de frequência, interferentes, deriva de fase/ganho, fading e canais de voz reais; medir recall **por classe** e taxa de falsa certeza em ruído.
3. Criar conjunto externo de gravações IQ, independentes do gerador, com licença/consentimento e rótulos confiáveis (modo, frequência, receptor, sample rate, sinal/ruído, gain). Particionar por **sessão, estação e equipamento**, não por janelas sobrepostas, para evitar vazamento.
4. Validar pipeline completo SDR→filtragem/canalização→48 kS/s→ONNX, inclusive sinais NFM, WFM, AM, CW, USB e LSB, agendador de worker/fila limitada, qualidade RF e CPU em Windows. Não alterar modo de recepção automaticamente com predições instáveis.
5. Manter o PR em rascunho até o relatório RF real e validação de segurança/latência. **Sem merge, sem nova release e sem anúncio de IA neural IQ em produção.**

Reprodução no GitHub Actions: workflow `.github/workflows/iq-model-export.yml`. Localmente, com Python 3.11, Torch CPU, onnx, onnxruntime e NumPy:

```bash
python scripts/train_iq_synthetic_ci.py
python scripts/export_iq_synthetic_v2.py --checkpoint models/iq/synthetic_v2.pt --output models/iq/synthetic_v2.onnx
PYTHONPATH=. python scripts/evaluate_iq_synthetic_stress.py --model models/iq/synthetic_v2.onnx --output models/iq/synthetic_v2_stress_metrics.json
python -m pytest -q tests/test_iq_classifier.py tests/test_iq_classifier_worker.py tests/test_iq_classifier_resampling.py tests/test_iq_classifier_contract.py
```
