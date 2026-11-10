# IQ/ONNX — Calibração e holdout separados por sessão

**Ferramenta de pesquisa; nenhuma gravação RF real foi homologada.** O modelo não deve selecionar o modo do receptor automaticamente.

Execute localmente, com os dois manifestos descritos em docs/IQ_RF_EVALUATION.md, separados por sessões independentes:

`python -m scripts.iq_session_gate --calibration-manifest meus_iq/calibracao.json --holdout-manifest meus_iq/holdout.json --root meus_iq --model models/iq/synthetic_v4.onnx --out gate_privado.json --max-unknown-far 0.10 --min-known-coverage 0.50`

O script rejeita sessões presentes em ambos os conjuntos, WAV repetidos por caminho e cópias idênticas por SHA-256. Cada conjunto precisa de sinais conhecidos e UNKNOWN de sessões separadas. Os limiares candidatos são 0,80, 0,90, 0,95, 0,99 e 0,999; **a escolha acontece exclusivamente na calibração**. O holdout só verifica a escolha já congelada.

O holdout exige **pelo menos três sessões independentes e dois dispositivos SDR distintos** antes de devolver `HOLDOUT_EVALUATED`. Se os limites empíricos forem satisfeitos, mas faltar diversidade, a decisão será `HOLDOUT_INSUFFICIENT_DIVERSITY` (código de saída 2). `holdout_diversity_gate_passed` registra esse portão separadamente. Os metadados declarados no manifesto **não provam** independência nem origem RF; é necessária conferência humana.\n\nAs taxas são apresentadas tanto por janela quanto como média entre sessões. O mecanismo exige um limite empírico de falsa aceitação de UNKNOWN e cobertura mínima de sinais conhecidos; se não houver limiar, devolve NO_ACCEPTABLE_THRESHOLD. Se o holdout falhar, devolve HOLDOUT_FAILED. Não seleciona outro limiar com base no holdout.

HOLDOUT_EVALUATED indica apenas que o limite empírico foi observado. **Não comprova acurácia operacional**, pois as janelas de uma sessão são correlacionadas, os rótulos dependem de verificação externa e as gravações podem não representar equipamentos, interferências e modos reais. A variável operationally_validated é sempre false.

Os arquivos IQ e seus identificadores permanecem locais. Não publicar manifestos privados nem gravações no GitHub.
