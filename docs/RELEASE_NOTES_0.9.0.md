# PT2VHF SDR Tool v0.9.0 — Entrega de validação

## Situação do problema de radiossonda
Na versão 0.8.0 o waterfall indicava atividade, porém a aba Sonda apenas importava JSON externo, sem receber o IQ do SDR. Isso impedia a decodificação direta no próprio aplicativo.

## Novo na v0.9.0
- Aba Decodificadores > RS41 · IQ ao vivo: mistura e decima o IQ do receptor atual para uma FI de +12 kHz em 48 kS/s e alimenta fsk_demod + rs41mod em processos independentes.
- Exibe ID/posição/altitude e dados decodificados de RS41; compartilha posições com mapa unificado da v0.8.0.
- Aba Satélites: TLE local, previsão SGP4 de passagens, azimute, elevação, distância e correção Doppler opcional somente RX.
- APRS iGate somente RX, habilitado pelo operador, com passcode, qAO, filtros anti-retransmissão e fila limitada.
- Idiomas com bandeiras PT-BR/EN/ES/FR/DE/IT/ZH: catálogo de traduções parcial de navegação e controles-chave.

## Pré-requisitos para testar uma radiossonda
1. Identifique o modelo da sonda. O pipeline IQ atual foi projetado para Vaisala RS41 (400–406 MHz); DFM/M10/M20/RS92 exigem outro decodificador.
2. Tenha os executáveis fsk_demod e rs41mod da radiosonde_auto_rx instalados no sistema. Eles NÃO estão inclusos nos instaladores.
3. Ligue o SDR no software, abra Decodificadores > RS41 · IQ ao vivo, configure a frequência RF correta e os caminhos para os dois executáveis; clique Receber e decodificar RS41 via IQ.
4. Confira os pacotes em tabela. Em caso de ausência, capture IQ para diagnóstico do protocolo, SNR, ganho, frequência real e eventuais perdas de amostras.

Referência técnica: https://github.com/projecthorus/radiosonde_auto_rx/wiki/RS----Auto_RX-JSON-Formats

## Não homologado
- Não houve teste com RF real ou binários de demodulação no ambiente do mantenedor; os testes de CI exercitam a conversão sintética de IQ e regras de protocolo.
- SSTV, DMR/D-STAR/C4FM, IA neural, tradução integral e voz traduzida, RDS, ACARS, ADS-B/AIS por DSP nativo, KiwiSDR e previsão de pouso permanecem no backlog.
- A publicação no site e a atualização OTA exigem validação separada após a release no GitHub.

## Robustez do IQ
- Filtro passa-baixas e redução de amostragem com estado contínuo entre blocos do SDR, mesmo com tamanhos variáveis.
- Teste sintético compara processamento monobloco e streaming, para evitar saltos de fase e perda de sincronismo do decodificador FSK.
