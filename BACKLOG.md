# Backlog — PT2VHF SDR Tool

Itens registrados pelo mantenedor. Não implementar até o pedido de versão nova.

## Pendentes

### Modo AUTO (registrado em 07/11/2026)
- Novo modo **AUTO** junto aos demais (NFM, WFM, AM, USB, LSB, CW…), também no display quando os modos
  forem para lá: detecta o tipo do sinal e aplica automaticamente modo, filtro e sintonia.
- Usar o detector já existente (`detect_mode`, botão "Detectar modo"), reavaliando ao mudar de frequência
  (clique no waterfall, memória, scanner) e sempre que houver sinal novo, sem trocas nervosas
  (histerese/confiança mínima); mostrar no display o modo detectado (ex.: "AUTO·NFM").
- Em SSB, combinar com a auto-sintonia pelos harmônicos da voz.

### Waterfall para ao mudar de banda com RTL-SDR Blog V4 e não volta (registrado em 07/11/2026)
- **Relato:** com um RTL-SDR Blog V4, ao mudar de banda o waterfall parou; voltando para 2 m continua parado.
  O waterfall tem que ficar contínuo enquanto o dispositivo estiver detectado.
- **Causa provável (código):** em `RtlSdrSource._run`, se `read_samples_async` termina sem exceção
  (erro de USB/sintonizador), `_running` continua verdadeiro; o motor espera blocos para sempre, sem aviso
  nem recuperação.
- **Corrigir:**
  - vigiar o fluxo (sem amostras por ~1 s): reabrir a leitura e, se preciso, o dispositivo, reaplicando
    frequência, ganho, ppm e bias-T;
  - avisar o usuário se não recuperar; nenhuma mudança de banda pode deixar o waterfall parado;
  - erro ao sintonizar uma frequência deve ser informado, mantendo a frequência anterior.
- **V4:** a `librtlsdr` incluída (pyrtlsdrlib, osmocom v0.8.0) provavelmente não suporta o V4 por completo
  (HF pelo upconverter interno, R828D). Embutir a biblioteca do driver RTL-SDR Blog e testar 2 m, PX e HF
  no V4. HF no V4 é pelo upconverter, não por "Amostragem direta".
- **Faixa sem suporte:** se o dongle não alcança a banda escolhida (ex.: HF num RTL-SDR comum), avisar
  em vez de travar.

### Modos clicáveis dentro do display LCD (registrado em 07/11/2026)
- Levar a seleção de modo (NFM, WFM, AM, USB, LSB, CW, DSB, RAW) para dentro do display de rádio,
  como teclas/indicadores clicáveis, com o modo ativo destacado (hoje o display só mostra o modo e a
  troca fica no painel "Modo / Filtro", numa aba atrás de "Receptor").
- Manter os atalhos Alt+N/W/A/U/L/C e o assistente "Detectar modo" funcionando junto.

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
