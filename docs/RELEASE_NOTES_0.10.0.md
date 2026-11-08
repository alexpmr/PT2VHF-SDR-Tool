# PT2VHF SDR Tool v0.10.0 — notas e checklist de homologação

## Mudanças implementadas

- Abas principais **ADS-B**, **AIS** e **Sondas Meteorológicas** separadas.
- A aba principal **Decodificadores** foi retirada; APRS, DTMF e CTCSS permanecem dentro de **Scanner**. APRS iGate RX foi removido da navegação e seu envio ao APRS-IS desabilitado.
- As teclas de seleção rápida das bandas foram movidas **para dentro do LCD**, alinhadas aos temas visuais, com faixa fora do SDR em cinza e botões de modo preservados.
- Sondas Meteorológicas concentra o pipeline de recepção RS41 por IQ e a importação de telemetria JSON externa; nenhum painel duplicado.
- Diagnóstico da RS41: contadores de blocos IQ e amostras, JSON, quadros com e sem GPS, perdas na fila, status FSK/RS41, informações de erro do stderr e captura limitada a 20 s de IQ complexo 48 kS/s (.c16).
- Decoder RS41 atualizado para sinalização de estatísticas FSK e subquadros JSON, conforme parâmetros de radiosonde_auto_rx.
- Mapas OSM com rastros por estação e exportação GPX/KML; CSV mantido.

## Limitações técnicas importantes

- **A falha de decodificação RS41 relatada pelo mantenedor não está homologada.** O pipeline exige **fsk_demod** e **rs41mod** instalados externamente; a simples presença de RF no waterfall não significa quadros válidos. Sem binários externos não existe decodificação. Não houve gravação de referência real validada nessa release.
- A captura .c16 da banda reduzida é útil para reproduzir o defeito com os mesmos decodificadores; o usuário deve verificar protocolo, ganho, ppm, frequência e estatísticas.
- ADS-B e AIS continuam com feeds externos de readsb/dump1090 e AIS-catcher/rtl_ais; não são receptores IQ nativos.
- Permanecem pendentes voz digital, SSTV, NOAA/Meteor, tradução integral, IA neural, WFM RDS, KiwiSDR e demais itens do backlog.
- Os testes CI não substituem teste com RTL-SDR/RS41 real; a publicação no site é uma etapa independente.

## Critérios de distribuição

1. Linux pytest: todos os testes aprovados e encerramento limpo.
2. Windows CI: pytest, PyInstaller Setup/Portable, autotestes dos executáveis e instalação silenciosa.
3. Release GitHub com SHA256SUMS.txt e assets identificados como v0.10.0.
4. Hostinger: /sdr e /updates.json com v0.10.0 e download.php com contagem; /update.php?product=sdr deve anunciar os dois pacotes e baixar bytes com hashes verificáveis.
5. Avisar explicitamente que o RS41 ainda necessita validação física e ferramentas externas.

