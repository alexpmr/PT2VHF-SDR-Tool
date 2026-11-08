# Build PT2VHF SDR Tool v0.8.0

Código integrado com a v0.7.0 aprovada. Recursos adicionados:
- Feeds ADS-B/readsb JSON e AIS/NMEA (!AIVDM), telemetria local de radiossondas.
- Painel de monitoramento e mapas OSM, CSV e configuração de atualização automática.
- CAT rigctld Hamlib TCP em segundo plano, sem controle PTT.
- Perfis de memória por cidade/região, com importação CHIRP.
- Formulários compactos de Configurações e Receptor.

Critérios de verificação para distribuição Windows:
1. Testes unitários Windows (inclusive fixtures AIS e CAT).
2. PyInstaller folder e portable; autoteste dos dois .exe.
3. Inno Setup e instalação silenciosa com autoteste.
4. Publicar a release GitHub somente com SHA256SUMS.
5. Só atualizar o site oficial e o OTA após validar arquivos públicos e manifesto.

Os testes no Linux podem terminar com falha nativa de Qt na saída do
interpretador apesar de pytest reportar todos os testes como aprovados;
investigar separadamente, sem ocultar o problema.
