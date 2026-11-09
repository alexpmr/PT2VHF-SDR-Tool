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
