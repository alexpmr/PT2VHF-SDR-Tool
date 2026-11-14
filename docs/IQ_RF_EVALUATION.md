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

O avaliador offline agora recusa saídas com classes ausentes, probabilidades não finitas/negativas ou softmax não normalizada, além de confiança fora de `[0, 1]`. As curvas de aceitação e os erros de alta confiança usam o **máximo das probabilidades brutas**. Além disso, o avaliador agora exige que `confidence` concorde com esse máximo (tolerância absoluta de 1e-6): metadados desatualizados provocam erro explícito, em vez de permitir um relatório RF de um classificador internamente inconsistente. A matriz de confusão continua usando o modo efetivo, inclusive UNKNOWN após o limiar configurado. Um modo conhecido (CW/AM/NFM/USB/LSB/WFM) deve coincidir com o argmax da softmax; se divergir, a avaliação falha em vez de publicar matriz de confusão contraditória. UNKNOWN continua permitido como decisão explícita de rejeição por confiança. **Quando o classificador expõe `min_confidence`**, o avaliador também exige consistência bidirecional com o limiar configurado: um modo conhecido abaixo dele e um UNKNOWN acima dele são recusados. Limiares não finitos ou fora de `[0, 1]` também são inválidos. Stubs externos sem esse atributo preservam a verificação anterior, sem presumir qual limiar foi aplicado. Esta validação de contrato é sintética, não prova desempenho RF. Testes com stubs sintéticos verificam essa consistência, sem validar a qualidade de RF real.

Execute vários modelos sobre os mesmos WAV sem enviar dados ao GitHub:

`python scripts/evaluate_iq_recordings.py --manifest meus_iq/manifest.json --root meus_iq --model models/iq/synthetic_v3.onnx --additional-model v4=models/iq/synthetic_v4.onnx --additional-model v5=models/iq/synthetic_v5.onnx --out comparacao_privada.json`

Validações extras: cada WAV só pode aparecer uma vez no manifesto; uma sessão não pode misturar SDRs; frequência não finita é rejeitada. Separe por sessão e dispositivo na validação externa; não use sessões de treinamento para estimar acurácia independente.


## Preparar os WAV IQ registrados pelo SDR Tool

A função **Gravar IQ** do programa registra WAV PCM16 estéreo na taxa original do SDR, com frequência central no nome. Para avaliar a IA, é necessário extrair **um canal IQ de 48 kS/s** centrado na frequência de interesse, preservando I e Q. WAV de áudio demodulado não serve.

O script experimental `scripts/prepare_iq_rf_capture.py` converte essas gravações offline, misturando a frequência para o centro com NCO contínuo e aplicando filtro FIR antialiasing antes da decimação. O arquivo original nunca é substituído. O script também acrescenta a gravação ao manifesto usado pelo avaliador ONNX.

Exemplo PowerShell, gravando com centro em 145,500 MHz e selecionando um sinal NFM a 145,5125 MHz:

~~~powershell
python -m scripts.prepare_iq_rf_capture --input "C:\IQ\PT2VHF_20261109_180000_145500000Hz_IQ.wav" --output "C:\IQ\onnx\session001_nfm.wav" --center-hz 145500000 --target-hz 145512500 --mode NFM --device "RTL-SDR V4" --session "session001" --root "C:\IQ\onnx" --manifest "C:\IQ\onnx\manifest.json"
~~~

Requer NumPy e SciPy e WAV IQ estéreo de 16 bits com taxa entre **48 kS/s e 3,072 MS/s**. Agora suporta conversão racional contínua (por exemplo, 1,024 e 2,048 MS/s → 48 kS/s), sem exigir múltiplos inteiros. Usa filtro FIR polifásico antialiasing, janelas com sobreposição e oscilador digital contínuo. Esta mudança foi validada inicialmente com sinais sintéticos, não com recepção RF real. O sinal precisa ficar dentro da faixa capturada, com margem de 24 kHz das bordas de Nyquist. **Mantenha a frequência central fixa** durante a gravação; se o receptor mudar de centro, faça uma nova sessão. Em capturas com squelch/VOX, podem ocorrer descontinuidades.

O modo indicado deve ser confirmado **independentemente** da rede neural. WFM não é suportado neste formato. O conversor apenas prepara arquivos para avaliação: não verifica a autenticidade da RF nem certifica os rótulos. Separe gravações e sessões de treinamento, calibração e holdout. Evite incluir sinais privados e não publique os WAV sem consentimento.


Consulte também docs/IQ_DATASET_AUDIT.md para a auditoria de qualidade e detecção de trechos repetidos entre sessões.

## Metadados de proveniência da captura IQ

O gravador desta branch experimental gera um sidecar no formato
nome.wav.iq.json ao finalizar a captura. Ele registra centro e taxa de
amostragem, VFO/mode iniciais, uso de VOX, contagem de frames e mudanças
de centro/taxa durante a gravação. Não contém amostras nem indicativos.

O conversor consulta o sidecar automaticamente, bloqueia capturas com
VOX, mudanças de centro, erros de amostragem ou metadados incompletos.
Nesse caso pode obter --center-hz do JSON; para WAVs legados sem sidecar,
--center-hz permanece obrigatório.

Estes metadados não são assinados nem provam RF real. O WAV do programa
já recebe remoção DC por bloco antes de ser escrito; o sidecar declara
esse processamento. Encerramentos abruptos podem deixar WAVs sem sidecar.

## Proteção contra interrupção e alteração de gravações

Na branch experimental, o gravador cria um sidecar `nome.wav.iq.json` com
`capture_state: recording` e `completed: false` **no início** da gravação.
Esse marcador é intencionalmente inadequado para o conversor. Após fechar
o WAV, o aplicativo calcula SHA-256 **do arquivo inteiro**, informa seu
tamanho e substitui atomicamente o sidecar pelo estado `complete`.

O conversor verifica o tamanho e o SHA-256 antes de preparar o IQ canalizado.
Uma divergência de conteúdo, arquivos com metadados incompletos ou gravações
interrompidas são rejeitados — inclusive quando `--center-hz` é informado.
Gravações antigas, sem sidecar, exigem centro manual; sidecars legados
(schema 1) permanecem aceitos, mas `capture_integrity_verified` será `false`.
Um arquivo novo e válido (schema 2) informa `capture_integrity_verified: true`.

Esse SHA-256 permite detectar corrupção ou alteração acidental. **Não é uma
assinatura digital nem autentica a origem RF**: uma pessoa pode trocar
deliberadamente WAV e JSON. O cálculo integral ocorre no encerramento do
arquivo, podendo introduzir atraso ao finalizar gravações muito extensas.
Evite usar essa funcionalidade em gravações prolongadas sem monitorar espaço
em disco e os limites do formato WAV RIFF.


## Interrupções de fonte e perda de blocos IQ

Na branch experimental, a gravação passa a registrar o contador de blocos
`dropped` da fonte SDR desde o início da captura, sem contar perdas anteriores.
**Qualquer incremento durante a gravação** é marcado como
`dropped_iq_blocks` e torna o WAV inadequado à validação de sinal contínuo.
Uma reinicialização inesperada do contador também invalida a sessão.

Se a fonte SDR parar inesperadamente ou lançar erro durante a leitura, o
motor finaliza a gravação IQ e identifica no sidecar o motivo
`source_stopped_unexpectedly` ou `source_read_failed`. O WAV é fechado e
recebe checksum, mas permanece `suitable_for_continuous_channelization: false`;
o conversor o recusa. Uma parada normal pelo botão não recebe esse motivo.

**Limitação de observabilidade:** `dropped` reflete perdas na fila de blocos
que a fonte informa. Não garante detectar todas as perdas internas do dongle,
interferência USB ou falhas de sincronismo não expostas pelo driver. O SHA-256
protege a integridade após a captura, mas não detecta amostras ausentes que já
chegaram faltando. Para validação conclusiva, comparar também sinais reais
com referência independente.


## Limite de gravações WAV RIFF (4 GiB)

WAV RIFF usa campos de 32 bits para os tamanhos dos dados. Capturas IQ
PCM16 estéreo consomem **4 bytes por amostra complexa**: a 2,4 MS/s isso
representa aproximadamente 9,6 MB/s, chegando perto de 4 GiB em pouco mais
de 7 minutos. A taxa real do SDR pode variar.

O gravador experimental interrompe automaticamente a captura **antes de
ultrapassar o tamanho RIFF seguro**. O WAV pode ser fechado normalmente, mas
o sidecar recebe `wav_riff_limit` e
`suitable_for_continuous_channelization: false`, pois a sessão foi truncada.
O aplicativo informa o motivo. Os arquivos originais não são sobrescritos.
O mesmo mecanismo identifica falha de escrita (`wav_write_failed`).

Para sessões longas, prefira diversas capturas curtas e independentes; não
interprete recortes automáticos como gravação contínua. Suporte a RF64/W64 ou
segmentação contínua exige projeto específico e ainda não foi implementado.


## Hash SHA-256 de gravações extensas sem bloquear a recepção

A partir desta revisão experimental, quando o arquivo WAV excede 64 MiB
ou quando sua finalização ocorre na thread de DSP, o cálculo SHA-256 é
executado em uma thread separada, após o WAV ser fechado. O sidecar fica
marcado como **`recording` / incompleto** até o cálculo e a escrita atômica
dos metadados terminarem. O conversor não aceita esse arquivo enquanto
estiver pendente.

O processo de finalização usa uma thread não daemon, para não descartar o
checksum em um encerramento normal. Finalizar arquivos extensos pode manter
o processo Python ativo mesmo após o fechamento da janela, enquanto conclui
a verificação. Encerramento forçado ou falta de energia ainda pode deixar
o marcador pendente; nesse caso, não utilizar o WAV como conjunto validado.


## Referência matemática e controle de memória

A conversão em blocos é comparada em testes com uma referência independente
que lê o WAV inteiro, mistura o canal para a banda-base e executa
`scipy.signal.resample_poly` de uma vez, incluindo amostras das extremidades
e trechos com ruído. Esse teste verifica a **implementação DSP**, não a
acurácia de identificação de modulação em RF real.

Para evitar consumo descontrolado de memória, o conversor recusa razões
racionais de reamostragem cujo numerador ou denominador reduzido exceda
**4.096**. Taxas SDR comuns como 1,024, 2,048, 2,4 e 2,4576 MS/s continuam
suportadas. Taxas quase coprimas com 48.000 Hz (por exemplo, 1.000.001 S/s)
são bloqueadas antes da alocação do FIR, com uma mensagem orientando usar
uma taxa de amostragem padrão do equipamento. Não há fallback de baixa
qualidade nem reamostragem silenciosamente aproximada.


## Portadoras CW/AM exatamente no centro do SDR (preservação IQ)

Na revisão experimental, o WAV bruto agora é gravado **antes** da remoção
por bloco da média complexa do IQ. A correção de DC continua em vigor para
áudio, espectro e recepção, preservando o comportamento do aplicativo. O
sidecar declara `dc_removed_per_processing_block: false` e
`iq_samples_kind: raw_before_receiver_dc_correction` para gravações novas.

**Por quê:** subtrair a média de cada bloco apaga irreversivelmente uma
portadora complexa estável exatamente em 0 Hz (sinal sintonizado no centro),
ainda que a transmissão seja legítima. O arquivo bruto preserva essa
informação para análise posterior. **Arquivos anteriores que já sofreram
essa subtração não podem ter a componente perdida restaurada.**

**Limitação:** um pico DC também pode ser produzido pelo próprio SDR,
principalmente em arquiteturas zero-IF. Nem o novo WAV nem o ONNX permitem,
sozinhos, distinguir uma portadora CW/AM verdadeira do espúrio DC do receptor.
O classificador v2–v5 continua usando pré-processamento com remoção da média,
compatível com seu treinamento; **não foi retreinado nem homologado para
identificar CW puro em zero beat**. Para ensaios, grave com o sinal deslocado
do centro, documente o offset e confirme o modo por método independente.


## Resíduos numéricos na normalização IQ/ONNX

O classificador experimental v2–v5 usa remoção da média antes de normalizar
o IQ. Em `complex64`, uma portadora exatamente constante pode deixar
resíduos da ordem do arredondamento de ponto flutuante. Sem proteção, esses
valores ínfimos poderiam ser amplificados para amplitude normalizada e
produzir predições aparentemente confiantes sobre algo que não contém
informação modulada suficiente.

O pré-processador agora exige que a energia **após** remover DC ultrapasse
um limiar absoluto de `1e-8` e também um limiar relativo de `1e-5` da
amplitude RMS original. Se não ultrapassar, gera erro explícito
`No usable RF signal` e **não executa inferência ONNX**. Sinais AM com
modulação mensurável continuam aceitos. Não altera os pesos dos modelos,
mas impede a falsa normalização de portadoras estáticas/espúrios DC.

Isso não resolve a identificação de CW/AM em zero beat, nem separa
portadora RF verdadeira do desvio DC do receptor. Essa distinção continua
a exigir sintonia deslocada e confirmação independente.
