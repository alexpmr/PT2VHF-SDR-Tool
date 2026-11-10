# Auditoria local de qualidade das gravações IQ

**Pesquisa experimental. PASS não significa que o sinal seja RF real nem que seu modo esteja correto.**

Antes de comparar os modelos ONNX em sessões de recepção, rode o auditor de IQ.
Ele lê WAV estéreo PCM16/48 kS/s e informa clipping, trechos em silêncio,
componentes DC, energia próxima das bordas de Nyquist, semelhança suspeita entre I e Q
e repetição exata de janelas IQ entre sessões. Resultados são heurísticos.

Exemplo no PowerShell, após preparar o manifesto com prepare_iq_rf_capture.py:

~~~powershell
python -m scripts.audit_iq_dataset --manifest C:\IQ\onnx\manifest.json --root C:\IQ\onnx --out C:\IQ\onnx\relatorio_qa_privado.json --max-windows 256
~~~

Resultados: **BLOCK** (dados inadequados ou reutilizados entre sessões),
**REVIEW** (precisa de inspeção do operador), **PASS** (sem as anomalias definidas).
BLOCK gera exit code 2, mas o relatório é salvo. REVIEW não deve ser considerado
aprovação automática. Gravações AM/CW podem ter portadoras em DC legítimas; por
isso o auditor não usa esse indicador para bloquear essas modulações.

Não envie gravações nem manifestos privados ao repositório. O relatório não
contém nomes de arquivo, indicativos, caminhos ou IDs de sessão, apenas
índices dos arquivos no manifesto, métricas e rótulos de modo declarados.
Repetições após deslocamento, reamostragem ou outra edição podem não ser
detectadas: esta auditoria é complementar à segregação por sessão do holdout.

Em qualquer resultado, rf_validated e operator_labels_verified continuam false.


## CW/AM no centro: sinal legítimo ou espúrio DC?

Um IQ com componente quase constante em 0 Hz pode conter uma portadora
CW ou AM real, mas também pode representar o desvio DC gerado pelo próprio
hardware zero-IF. Não há forma confiável de distinguir os dois usando
somente o vetor IQ dessa gravação. Por isso, nos rótulos **CW** e **AM**, a
auditoria passa a marcar `REVIEW: centered_carrier_or_hardware_dc_spur` ou
`REVIEW: constant_cw_am_or_hardware_dc`, em vez de assumir que se trata
de um sinal válido ou de rejeitá-lo apenas por ser constante. O operador
deve confirmar a transmissão com referência independente ou deslocamento
de sintonia. Para `UNKNOWN`, um arquivo quase constante continua bloqueado
como dado inadequado para aferir reconhecimento de sinais desconhecidos.

Uma classificação `REVIEW` não atende por si só à homologação operacional.
O classificador v2–v5 ainda remove a média IQ como parte de seu contrato;
preservar a portadora nos WAV brutos não corrige os pesos dos modelos.
