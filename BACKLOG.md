# Backlog — PT2VHF SDR Tool

Itens registrados pelo mantenedor. Não implementar até o pedido de versão nova.

## Pendentes

### Waterfall não acompanha ao arrastar para o lado (registrado em 07/11/2026)
- **Relato:** ao clicar e arrastar o waterfall para o lado, a tela continua mostrando o waterfall da região
  anterior; a nova região só aparece depois de clicar nela (o clique sintoniza e muda a frequência central).
- **Esperado:** arrastar (pan) deve atualizar a região mostrada, como no KiwiSDR/SDR#: ao sair da faixa
  recebida, mudar a frequência central do receptor para a região visível e o waterfall acompanhar.
- **Pista:** hoje o arraste só move a visualização (pyqtgraph) dentro da faixa já amostrada; não há
  re-sintonia do centro quando a área visível sai da largura de amostragem.

### OTA igual aos demais programas PT2VHF (registrado em 07/11/2026)
- Alinhar a atualização automática ao comportamento dos outros programas (ex.: Sat Tool, Prog Tool,
  QSL Manager): fluxo e textos do aviso de versão nova, adiamento, progresso, instalação e reabertura,
  sempre via `https://www.pt2vhf.com/update.php?product=sdr`, contando uma vez no `download.php`.
- Antes de implementar: comparar com o código de OTA desses programas e listar as diferenças.

### Instalador igual ao dos demais programas (registrado em 07/11/2026)
- Revisar o instalador (Inno Setup) e o portátil para seguir o padrão dos outros programas PT2VHF
  (nome dos arquivos, telas, idioma, ícones/atalhos, desinstalação e metadados).
- Antes de implementar: comparar com os instaladores publicados no site e listar as diferenças.

## Concluídos
- 0.3.0 — IA/assistente para SSB (auto-sintonia pelos harmônicos da voz, detecção de modo e banda lateral,
  filtro adaptativo, transcrição local opcional), voltar no tempo, receptores extras, instalador/portátil
  Windows e atualização automática pelo www.pt2vhf.com.
- 0.2.0 — memórias prontas, favoritos, scanner por espectro e gravação por atividade.
- 0.1.0 — primeira versão.
