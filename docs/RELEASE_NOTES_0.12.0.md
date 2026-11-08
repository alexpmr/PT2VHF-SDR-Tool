# PT2VHF SDR Tool v0.12.0 — IA neural e transcrição local

## Implementado
- RNNoise por pyrnnoise (RNN local): pós-processamento de áudio de voz a 48 kHz, controle de mistura seca/tratada, worker limitado para não bloquear RF. NFM/AM/USB/LSB/DSB recebem tratamento; WFM, CW e RAW não.
- Integração de saída: alto-falante, streaming local no navegador, gravação contínua e legendas recebem áudio tratado quando o RNNoise está ativado. Demodulação APRS/DTMF/CTCSS, S-meter, waterfall, gravação IQ e gravação de atividade continuam com RF/áudio original.
- faster-whisper/CTranslate2 disponível como backend de inferência de fala em CPU no aplicativo compilado. Modelos tiny/base/small baixados explicitamente em Scanner → Legendas ao vivo, salvos no perfil do usuário; modelo não é baixado ao abrir ou ativar o app. Após download, uso inteiramente offline.
- Legendas por blocos com frequência, modo, horário, idioma e indicativos; histórico e exportação CSV, além de transcrição de WAVs do Scanner. O reconhecimento não é determinístico nem transcreve fonia cifrada/digital sem decoder.
- Perfil Sinal fraco liga NR/NB/AGC e RNNoise quando possível.

## Testes obrigatórios
- 108+ testes anteriores e novos testes de IA em Linux (Qt offscreen) e Windows.
- Autoteste Setup e Portable exigindo importação/inferência do RNNoise e importação de faster-whisper/CTranslate2.
- Setup Inno instalado silenciosamente com aplicativo funcional.
- SHA256SUMS.txt compatível com os 2 pacotes gerados e release GitHub v0.12.0.
- Validação manual SDR em HF, VHF/UHF, voz com ruído em SSB/FM, CPU e latência, e teste do download e transcrição offline no Windows.

## Limitações
- Modelo Whisper é uma etapa de download voluntário e não acompanha instalador.
- IA neural atua após demodulação; não melhora o sinal IQ nem recupera pacotes perdidos.
- RNNoise pode criar artefatos, especialmente em voz muito fraca; preserve a opção de desligar e comparar.
- Tradução, SSTV, CW neural, demoduladores de voz digital e melhorias de IA de IQ seguem no backlog.
- Site e OTA só são concluídos quando o domínio www.pt2vhf.com servir o manifesto correto.
