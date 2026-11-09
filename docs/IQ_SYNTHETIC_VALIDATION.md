# Validação experimental IQ → ONNX — 09/11/2026

**Estado:** somente branch `feature/iq-signal-classifier`, PR #2 em rascunho. Não foi integrado à `main` nem publicado em instaladores. **Nenhuma acurácia com RF real foi medida.**

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
