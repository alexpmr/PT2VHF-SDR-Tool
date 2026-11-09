# Validação do IQ/ONNX com gravações RF reais

**Estado:** ferramenta offline criada, sem gravações reais fornecidas. Os testes automatizados utilizam WAV sintéticos apenas para validar leitura, segurança e métricas; eles não demonstram acurácia RF.

## Preparação dos dados

Grave sinais de modo confirmado (CW, AM, NFM, USB, LSB e ruído UNKNOWN) como **WAV IQ PCM16 estéreo 48.000 Hz**, com I no canal esquerdo e Q no direito. As amostras precisam estar **centradas/canalizadas** no sinal. WAV de áudio demodulado e gravações de banda larga a 240 kS/s/2,4 MS/s não são válidos diretamente. WFM não está suportado por este contrato.

Crie `meus_iq/manifest.json` com caminhos relativos à pasta de gravações:

```json
{
  "recordings": [
    {"path":"am001.wav","mode":"AM","session_id":"dia1-sessao1","device":"RTL-SDR V4","frequency_hz":145650000},
    {"path":"nfm001.wav","mode":"NFM","session_id":"dia2-sessao2","device":"Airspy","frequency_hz":145430000}
  ]
}
```

Com o modelo experimental baixado do GitHub Actions, execute na raiz do projeto:

```bash
python scripts/evaluate_iq_recordings.py --manifest meus_iq/manifest.json --root meus_iq --model models/iq/synthetic_v4.onnx --out resultado_rf_privado.json
```

O relatório traz matriz de confusão, recall por classe, erros com confiança elevada, número de sessões, dispositivos e média de acurácia por sessão. Não inclui nomes de arquivos, IDs de sessão ou frequência.

**Atenção:** as janelas dentro de uma mesma sessão são correlacionadas. Use sessões e equipamentos diferentes, ruído sem transmissão e SNR variados. Três sessões e dois SDRs são um ponto de partida, não condição suficiente para homologação. A confirmação do modo não pode depender da predição do próprio classificador.

Não faça commit dos WAV, manifestos privados ou capturas contendo informações sensíveis.


## Comparação de modelos e controle de falsos positivos

O relatório separa janelas de sinal conhecido e UNKNOWN. Nos limiares de 80%, 95% e 99%, informa sinais válidos aceitos corretamente, erros aceitos, cobertura e falsa aceitação de UNKNOWN. Uma classe ausente retorna `null`, não zero fictício.

Execute vários modelos sobre os mesmos WAV sem enviar dados ao GitHub:

`python scripts/evaluate_iq_recordings.py --manifest meus_iq/manifest.json --root meus_iq --model models/iq/synthetic_v3.onnx --additional-model v4=models/iq/synthetic_v4.onnx --additional-model v5=models/iq/synthetic_v5.onnx --out comparacao_privada.json`

Validações extras: cada WAV só pode aparecer uma vez no manifesto; uma sessão não pode misturar SDRs; frequência não finita é rejeitada. Separe por sessão e dispositivo na validação externa; não use sessões de treinamento para estimar acurácia independente.
