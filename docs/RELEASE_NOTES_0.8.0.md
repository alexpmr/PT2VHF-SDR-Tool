# PT2VHF SDR Tool v0.8.0 — Notas de versão

## Implementado
- Monitor de aviões ADS-B (ICAO, indicativo, altitude, velocidade, rumo, coordenadas) importando aircraft.json de readsb/dump1090. Feed gerado externamente.
- Monitor AIS com decodificação de mensagens NMEA !AIVDM, posição tipo 1/2/3/18/19, e identificação tipo 5.
- Monitor de radiossondas que importa JSON local com ID, posição, altitude, velocidade vertical/horizontal e campos meteorológicos compatíveis.
- Mapa unificado OpenStreetMap e exportação CSV por tipo de tráfego, com arquivos locais.
- Controle CAT por Hamlib rigctld: leitura/sincronização opcional de frequência e modo do transceptor e envio manual sem PTT.
- Bancos de memórias por região/cidade, com salvamento, carregamento confirmado e importação CSV CHIRP por região.
- Correções de largura em campos de configurações.

## Uso
1. Aba Decodificadores → ADS-B / AIS / Sondas: configure o caminho do arquivo gerado pelo **decodificador externo** e clique Atualizar agora ou marque atualização automática.
2. CAT: instale/configure Hamlib rigctld separado; acesse Configurações → CAT · Hamlib, informe host e porta e use os botões.
3. Memórias / Varredura → Região de escuta: salve a região atual, importe CHIRP por região ou ative outra região, substituindo o banco corrente após confirmação.
4. Mapa abre um HTML local, mas exige Internet para os tiles OpenStreetMap.
5. Os feeds externos não alteram a sintonia do RTL-SDR; usar receptores compatíveis paralelos se necessário.

## Limitações e backlog pendente
- Não existe decodificação RF direta para ADS-B, AIS, RS41, SSTV, DMR, D-STAR ou C4FM.
- Não existem modelo de IA neural embarcado, tradução automática local, catálogo completo de idiomas, Doppler orbital, previsão física de queda de radiossondas, RDS, ACARS e outros decodificadores avançados.
- Teste com equipamento real, compatibilidade dos processos externos e Windows Setup/Portable exigem validação da release.
- Distribuição no site oficial e OTA só podem ser declaradas concluídas depois de conferir os binários e os metadados públicos.
