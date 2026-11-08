# Critérios de aceitação — classificador IQ experimental

## Status
Modelo sintético em desenvolvimento. **Não homologado para recepção SDR real.**

## Bloqueios antes de uma release operacional
1. Exportar ONNX e verificar paridade com PyTorch (erro absoluto máximo 1e-4).
2. Executar testes de carregamento e inferência via ONNX Runtime.
3. Registrar matriz de confusão e precisão/recall por classe em conjunto de validação separado.
4. Validar com gravações IQ reais de CW, AM, NFM, WFM, USB, LSB e sinais desconhecidos, incluindo SNR baixo e deslocamento de sintonia.
5. Confirmar que a taxa de amostragem de entrada é idêntica à usada no treinamento. **O gerador sintético atual usa 48 kHz; o motor de captura IF do aplicativo usa 240 kHz. Sem reamostragem/treinamento compatível, as previsões não são confiáveis.**
6. Confirmar que o modelo consegue separar WFM com largura real de dezenas de kHz; a simulação atual de WFM em 48 kHz não representa fielmente a banda de RF de radiodifusão.
7. A interface deve apresentar confiança e permitir confirmação manual, sem alterar modo ou VFO automaticamente.
8. Avaliar CPU, latência e descarte de quadros com hardware SDR conectado.

## Métricas
Acurácia sintética é uma métrica de desenvolvimento, não um indicador de homologação.
O pipeline deve preservar as métricas como artefato. Não declarar conclusão de treinamento ou exportação antes de verificar os jobs.

## Segurança operacional
Ausência de modelo ONNX, entrada inválida e confiança abaixo do limiar devem resultar em classificação desconhecida ou erro explícito; nunca em modo inventado.
