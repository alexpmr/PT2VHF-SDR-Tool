# Backlog — PT2VHF SDR Tool

Itens registrados pelo mantenedor. Não implementar até o pedido de versão nova.

## Pendentes

### Painel Áudio / DSP sem barra de rolagem horizontal (registrado em 07/11/2026)
- O bloco da direita (Áudio / DSP) mostra barra de rolagem horizontal: o conteúdo é mais largo que o painel
  (vê-se na captura da 0.3.0: equalizador cortado em "3.2k", campos de NB/Notch encostados na borda).
- Reorganizar os elementos para caber sempre na largura do painel, sem rolagem horizontal: linhas que hoje
  juntam rótulo + controle + botão passam a quebrar em duas, sliders do equalizador com largura flexível,
  campos com largura mínima menor; só a rolagem vertical continua (quando a altura não couber).
- Conferir em 1366×768, 1600×900 e 1920×1080, e com o painel estreito.

### Aba Configurações + servidor web para acompanhar a sessão pela rede (registrado em 07/11/2026)
- Criar a **aba/janela Configurações** reunindo as opções do programa (hoje espalhadas pelos painéis).
- Nela, opção **Servidor web (rede local)**, como no PT2VHF APRS Client (conferir a implementação "web
  local/LAN" de lá e seguir o mesmo padrão: porta, endereço exibido/QR, acesso só na LAN, senha opcional).
- Outro navegador/computador da rede **replica a sessão corrente**: display LCD (frequência, modo, S-meter),
  waterfall/espectro, memórias/favoritos, scanner e decodificadores (APRS), e **o áudio sai também no
  navegador remoto** (streaming, ex.: WebSocket com áudio comprimido), sem deixar de tocar no computador local.
- Definir permissões: só visualizar/ouvir ou também controlar (sintonia, modo, volume); vários clientes ao
  mesmo tempo; baixo uso de CPU/banda (waterfall reduzido para o navegador).

### Gravação tipo VOX mais acessível (registrado em 07/11/2026)
- **Já existe desde a 0.2.0:** Scanner → aba "Atividade gravada" → "Gravar automaticamente cada transmissão
  (quando o squelch abre)" — um WAV por transmissão, descartando as curtas demais. O mantenedor pediu o recurso
  sem saber dele: falta visibilidade.
- **Melhorias:**
  - opção **VOX** junto ao botão "Gravar áudio" (painel Áudio / DSP) e indicador no display;
  - se o squelch estiver aberto, avisar e oferecer o squelch automático (sem squelch tudo seria gravado);
  - pré-gravação (~0,5 s antes de abrir) para não cortar o início da fala;
  - opção de juntar as transmissões num único arquivo por sessão (sem os silêncios) ou um arquivo por transmissão;
  - VOX também para a gravação de IQ.

### Três modos de layout: Essencial, Intermediário e Avançado (registrado em 07/11/2026)
- Seletor de layout (menu Exibir e/ou barra) que mostra ou esconde recursos conforme o nível,
  lembrando a escolha entre sessões.
- Sugestão inicial (a validar com o mantenedor):
  - **Essencial:** display LCD, waterfall, modos, volume/squelch, favoritos e memórias prontas.
  - **Intermediário:** + scanner, decodificadores, equalizador, gravação, assistente de sintonia.
  - **Avançado:** tudo (ganho/ppm/bias-T, NB/NR/notch, voltar no tempo, receptores extras, FFT,
    paletas e demais ajustes finos).
- Trocar de nível não perde configurações; "Restaurar layout padrão" respeita o nível escolhido.

### Auto-sintonizar ao selecionar uma transmissão (registrado em 07/11/2026)
- Ao selecionar uma transmissão (clique no waterfall/espectro, scanner, memória) e a frequência não estiver
  exatamente na dela, ajustar automaticamente para a frequência correta.
- Por modo: portadora (AM/CW), centro do sinal (NFM/WFM, inclusive estações com desvio de frequência) e,
  em SSB, a portadora suprimida pelos harmônicos da voz (auto-sintonia SSB já existente).
- Reaproveitar o assistente atual (`detect_mode`/`occupied_band`/`estimate_ssb_offset`), que hoje só roda
  pelos botões; opção para ligar/desligar e indicação no display da correção aplicada.
- Relaciona-se com o modo AUTO (que também escolhe o modo).

### Anúncio ao abrir o app, como nos demais programas (registrado em 07/11/2026)
- Ao abrir, mostrar o aviso/anúncio no mesmo padrão dos outros programas PT2VHF: divulgar o site oficial
  www.pt2vhf.com (downloads e atualizações somente por lá) e os demais aplicativos PT2VHF.
- Antes de implementar: conferir como os outros programas exibem esse anúncio (textos, frequência,
  opção de não mostrar de novo, ordem em relação ao aviso de versão nova) e seguir o mesmo comportamento.

### Modo AUTO (registrado em 07/11/2026)
- Novo modo **AUTO** junto aos demais (NFM, WFM, AM, USB, LSB, CW…), também no display quando os modos
  forem para lá: detecta o tipo do sinal e aplica automaticamente modo, filtro e sintonia.
- Usar o detector já existente (`detect_mode`, botão "Detectar modo"), reavaliando ao mudar de frequência
  (clique no waterfall, memória, scanner) e sempre que houver sinal novo, sem trocas nervosas
  (histerese/confiança mínima); mostrar no display o modo detectado (ex.: "AUTO·NFM").
- Em SSB, combinar com a auto-sintonia pelos harmônicos da voz.

### PRIORIDADE — Mudar de banda para a recepção e trava o programa (RTL-SDR Blog V4) (registrado em 07/11/2026)
- **Novo relato (07/11/2026):** dependendo da banda escolhida, para de receber e **a aplicação trava**
  (não só o waterfall). Mesmo item do relato anterior, mais grave.
- **Pontos prováveis de travamento (código):** a troca de frequência (`set_center_freq` da librtlsdr) roda
  na thread DSP ao mesmo tempo que a leitura assíncrona; se o USB/sintonizador não responde, a thread fica
  presa. Ao desligar, a interface espera a thread (`engine.stop`, 3 s) e depois chama `sdr.close()` na
  própria thread da interface, que pode bloquear indefinidamente → janela congelada.
- **Corrigir também:** nenhuma chamada à librtlsdr na thread da interface; trocas de frequência/ganho
  serializadas numa única thread do dispositivo, com tempo limite; se o dispositivo não responder,
  abandonar a leitura, avisar e oferecer reconexão sem congelar a janela; testar todas as bandas do
  seletor no V4 (incluindo HF) e num RTL-SDR comum.

#### Relato anterior: waterfall para ao mudar de banda com RTL-SDR Blog V4 e não volta
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
- **Observação do mantenedor (07/11/2026):** ao arrastar, a área nova que entra na tela fica **preta**;
  clicando em **Zoom: Total** volta a mostrar tudo. Confirma a pista: o arraste leva a visualização para
  fora da faixa recebida (sem dados = preto) e "Total" só reenquadra a faixa já amostrada.
  Corrigir: arrastar deve re-sintonizar o centro para a região visível (dados reais no lugar do preto);
  enquanto o receptor muda, não exibir área vazia.

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
