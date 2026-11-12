# Critérios de aceitação — classificador IQ experimental

## Status
Modelo sintético em desenvolvimento. **Não homologado para recepção SDR real.**

## Bloqueios antes de uma release operacional
1. Exportar ONNX e verificar paridade com PyTorch (erro absoluto máximo 1e-4).
2. Executar testes de carregamento e inferência via ONNX Runtime.
3. Registrar matriz de confusão e precisão/recall por classe em conjunto de validação separado.
4. Validar com gravações IQ reais de CW, AM, NFM, USB, LSB e sinais UNKNOWN, incluindo SNR baixo, deslocamento de sintonia e portadora não modulada. WFM permanece fora do escopo do contrato de 48 kS/s.
5. Confirmar a cadeia de taxas de amostragem: o treinamento usa 48 kS/s e a captura IF pode fornecer 240 kS/s. O worker reamostra para 48 kS/s **na thread de inferência**, não na thread de alimentação SDR, mas isso não demonstra ausência de aliasing nem fidelidade RF. Testar a cadeia completa com gravações reais independentes.
6. Não oferecer WFM como modo homologado: a janela de 48 kS/s não representa adequadamente a largura de banda da FM comercial. Qualquer suporte futuro requer captura, modelo e validação apropriados.
7. A interface deve apresentar confiança e permitir confirmação manual, sem alterar modo ou VFO automaticamente.
8. Avaliar CPU, latência ponta a ponta, fila e descarte de quadros com hardware SDR conectado. O teste sintético confirma apenas que a reamostragem FIR foi deslocada de `feed()` para o worker; não mede desempenho nem garante tempo real.

## Métricas
Acurácia sintética é uma métrica de desenvolvimento, não um indicador de homologação.
O pipeline deve preservar as métricas como artefato. Não declarar conclusão de treinamento ou exportação antes de verificar os jobs.

## Segurança operacional
Ausência de modelo ONNX, entrada inválida e confiança abaixo do limiar devem resultar em classificação desconhecida ou erro explícito; nunca em modo inventado.

## Política de diagnósticos Windows (12/11/2026)

O job `windows-tests` continua obrigatório e **fail-closed** na branch
`feature/iq-signal-classifier`: qualquer `Windows fatal exception`,
mesmo após `N passed`, reprova o CI. Isso **não** constitui uma correção
da corrupção de memória.

Os jobs `windows-crash-isolation` (matriz de 6 casos) e
`windows-file-probe` repetiam resultados já observados em múltiplos
commits. A partir desta revisão, ficam **desabilitados em push/PR comum**.
Para executá-los sob **hipótese nova**, usar GitHub Actions →
`Testes (build Windows sob demanda)` → `Run workflow`, selecionar a
branch experimental e habilitar `diagnose_windows`. Esses jobs somente
executam se o job Windows obrigatório falhar. O padrão é `false`.
Não habilitar `build_windows`; a geração de instaladores continua
restrita à `main`.

Este ajuste reduz custo e ruído do CI, mas **não prova estabilidade Windows**
nem resolve AMD/Intel, OOD/UNKNOWN, CW/AM, latência ou RF real. Resultados
anteriores não devem ser contados como novas medições. Se surgir um novo
padrão de falha, documentar a hipótese e habilitar a coleta manual dirigida.


Para reduzir execução redundante de commits intermediários, o workflow cancela
**apenas** runs de push anteriores da mesma branch experimental quando chega
um novo commit. Não cancela jobs da `main` nem verificações de evento PR.
Uma execução cancelada não fornece resultado QA; somente o CI do HEAD final
pode ser usado como evidência.
