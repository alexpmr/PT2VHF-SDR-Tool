# Lacunas pendentes — PT2VHF SDR Tool

> Gerado pelo Revisor em 28/11/2026. Lacunas que continuam abertas depois da revisão. As que dependem de decisão estão em [questions.md](questions.md); as demais dependem de teste com hardware real e não se resolvem por resposta.

## Base da extração
- 🔴 Specs descrevem a `main` v0.13.3; a versão publicada é v1.0.9 (156 commits, 58 arquivos à frente). Ver Pergunta 1.

## Homologação com hardware real (não respondível por chat)
| Unit | Lacuna |
|---|---|
| radiossonda-rs41 | Serial, posição e altitude de uma RS41 real no mapa (P0) |
| atualizacao-ota | Atualização ponta a ponta no Windows real, instalador e portátil (P0) |
| cat-rigctl | Leitura e escrita com transceptor e rigctld reais |
| display-e-instrumentos | Calibração do S-meter (offset −45 dB nominal); homologação visual do LCD |
| demodulacao-e-audio | Qualidade de áudio por modo com RF real |
| aprs-packet | Taxa de decodificação com RF real |
| assistente-de-sintonia | Acerto do AUTO com RF real |
| scanner-e-ocupacao | Detecção com antenas e sinais reais |
| reducao-de-ruido-neural | Qualidade, CPU e latência do RNNoise |
| legendas-e-transcricao | Qualidade do Whisper e reconhecimento de indicativos |
| recepcao-sdr | Watchdog com rtl_tcp e SoapySDR sob falha; testes de `rtl_driver.py` e SoapySDR |

## Defeitos ou riscos de código registrados
- 🔴 `memorias-e-favoritos`: JSON de memórias corrompido impede a abertura do programa (`memory.py:114-126`).
- 🔴 `recepcao-sdr`: `SourceError` de rtl_tcp/SoapySDR fora da faixa não é tratado (dívida D2).
- 🔴 `painel-web`: falta teste que garanta que nenhuma rota de escrita apareça.

## Backlog não implementado nesta base (pode já existir na v1.0.9)
- 🔴 Auto de níveis contínuo do waterfall; favoritos em menu suspenso e por uso; ADS-B e ACARS nativos.
