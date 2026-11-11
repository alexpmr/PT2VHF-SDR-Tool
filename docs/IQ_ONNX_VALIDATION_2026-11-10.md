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
