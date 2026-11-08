# Changelog

Todas as mudanças relevantes do PT2VHF SDR Tool.

## [0.7.0] — 2026-11-08
### Implementado
- Dois medidores analógicos vetoriais com ponteiros suavizados: S-meter calibrado em dBm / S-units e VU do áudio em dBFS.
- Três estilos de instrumento com exemplos em Configurações → Display: Valvulado, Militar e Estúdio.
- Histórico persistente de detecções do scanner em janela móvel de 24 horas; mapa de calor por frequência (12,5 kHz) e hora, com CSV. Não é medida contínua de ocupação.
- Perfil "Sinal fraco · DSP" com NB, NR e AGC, reversível ao desligar. Usa DSP clássico, **não** IA neural.
- Legendas locais da fonia demodulada, por trechos de ~4 segundos, com histórico, frequência, modo, idioma e indicativos, e exportação CSV. Funciona quando faster-whisper/modelo estão instalados (opcional, não embarcado).
- Ampliação da suíte de testes e limpeza de recursos de interface no CI.

### Permanece pendente
- IA neural real (RNNoise/DeepFilterNet), tradução da fala para outros idiomas, instalação automática de modelos, idiomas completos da interface, decodificadores de ADS-B/AIS/SSTV/DMR/D-STAR/C4FM e radiossondas.
- Testes com RTL-SDR real e validação dos pacotes Windows antes de publicar no site.

## [0.6.0] — 2026-11-08
### Adicionado
- Acesso rápido a bandas junto ao display; 60 m e memória de frequência/modo por banda.
- Bandas incompatíveis com o SDR identificado são exibidas esmaecidas; clique informa o motivo.
- Botão Centralizar (Ctrl+E) no waterfall, sem perder o zoom, com opção Seguir VFO.
- Primeira execução prefere RTL-SDR e interface Avançada; orientações no painel do receptor.
- Menus de configuração compactos, sem ocupar a largura total do painel.
- Testes de regressão para configuração inicial, painel de bandas e zoom.

### Observação
- Os itens extensos do backlog (modelos locais de IA, decodificadores externos, fonia digital,
  tradução em tempo real, radiossondas e temas analógicos) permanecem pendentes de implementação e testes.
- A versão 0.6.0 deve ser empacotada no pipeline Windows e validada com SDR real antes da publicação oficial.

## [0.5.0] — 2026-11-07
### Corrigido
- **RTL-SDR voltou a abrir** (0.4.1: "Error code -1 when setting PLL dithering mode" seguido de LIBUSB_ERROR_ACCESS):
  funções que a DLL do driver RTL-SDR Blog não tem passam a responder sem erro, e se a abertura falhar o dongle é
  liberado antes de tentar a biblioteca padrão.

### Adicionado
- **Abas superiores**, no padrão dos programas PT2VHF: Receptor (display + waterfall + áudio), Memórias / Varredura,
  Scanner, Decodificadores, Receptores extras e **Configurações** (sub-abas Receptor, Modo / Filtro e
  Geral · Web · Atualizações). Atalhos Ctrl+1…6.
- **Cabeçalho** com nome e versão, botão de **atualização no topo** (verificar / nova versão / progresso),
  resumo do receptor, **Ligar/Desligar** e relógio UTC.
- **Lembrar o receptor ao sair**: se o programa foi fechado com um RTL-SDR, rtl_tcp ou SoapySDR ligado, ele reconecta
  sozinho ao abrir (mesmo dispositivo, taxa, ganho e frequência); sem o dispositivo, avisa sem travar.
  Opção "Reconectar o receptor ao abrir".
- **Modo apresentação** (F11, Exibir ou botão "Tela cheia"): tela cheia sem barra de título e barra de tarefas, no
  monitor da janela; opcionalmente só display + waterfall. Esc/F11 saem; o programa lembra se estava nele.
- Interface web: opção **"Exigir chave na rede local"** — desmarcada, outro computador abre direto por
  `http://IP:porta/` (somente endereços de rede privada).

### Alterado
- Os botões de modo saíram do painel Modo / Filtro (ficam no display e nos atalhos Alt+…).
- Painel de áudio pode ser ocultado (Exibir) e redimensionado.

## [0.4.1] — 2026-11-07
### Corrigido
- **RTL-SDR não abria na 0.4.0 (LIBUSB_ERROR_ACCESS)** em computadores onde a 0.3.0 funcionava: se a biblioteca do
  driver RTL-SDR Blog não conseguir abrir o dongle, o programa usa automaticamente a biblioteca padrão (a da 0.3.0)
  e avisa qual foi usada.
- Ao desligar e ligar de novo, espera o dongle ser liberado antes de reabrir.

### Adicionado
- Configurações → **Biblioteca do RTL-SDR**: Automático, Driver RTL-SDR Blog ou Padrão.
- Mensagem de erro com explicação do "acesso negado" e o driver instalado em cada interface do dongle (Windows).

## [0.4.0] — 2026-11-07
### Corrigido
- **Mudar de banda não trava mais o programa** (relatado com RTL-SDR Blog V4): a interface nunca chama o dongle;
  os ajustes passam por uma fila com tempo limite; um vigia percebe quando as amostras param, reconecta
  sozinho e reaplica frequência, ganho, ppm e bias-T; frequência fora do alcance do dongle é recusada com aviso.
- Ao arrastar o waterfall para fora da faixa recebida, o receptor passa a cobrir a região visível
  (não fica mais preta até clicar em "Total").
- Painel Áudio / DSP sem rolagem horizontal (os controles se ajustam à largura).

### Adicionado
- **Driver RTL-SDR Blog** incluído no Windows (suporte completo ao V4, HF pelo conversor interno).
- **Preparar RTL-SDR**: instala o driver WinUSB (como o Zadig) pelo instalador ou pelo menu Ajuda;
  **Diagnóstico do RTL-SDR**.
- **Modo AUTO**: detecta o tipo da transmissão e aplica modo, filtro e sintonia ("AUTO·NFM" no display).
- **Auto-sintonizar ao selecionar** uma transmissão (clique, memória, scanner): portadora em AM/CW, centro
  do sinal em FM (encaixado no canal) e portadora suprimida em SSB pelos harmônicos da voz (tecla A-SINT).
- **Teclas ◀ ▶** para saltar para a transmissão vizinha, já sintonizada.
- **Modos clicáveis dentro do display** (AUTO, NFM, WFM, AM, USB, LSB, CW, DSB, RAW).
- **Três níveis de interface**: Essencial, Intermediário e Avançado.
- **Gravação VOX**: só grava com transmissão, com 0,5 s de pré-gravação; arquivo único sem os silêncios
  ou um por transmissão; VOX também para IQ.
- **Aba Configurações** e **interface web** (local ou rede LAN com chave): o navegador replica display,
  waterfall e APRS e toca o áudio, que continua saindo no computador.
- **Anúncio ao abrir** divulgando o site e os aplicativos PT2VHF.

### Alterado
- **OTA no padrão dos programas PT2VHF**: botão de versão, verificação automática, instalação automática quando
  o programa está livre (ou "Atualizar agora / Depois" com adiamento de 24 h), auxiliar externo que instala e
  reabre, e resultado mostrado na abertura seguinte.
- **Instalador no padrão dos programas PT2VHF**: instalação por usuário (sem administrador), opção de preparar o
  RTL-SDR, nomes `PT2VHF-SDR-Tool-vX.Y.Z-Win11-x64-Setup.exe` / `-Portable.exe`.

## [0.3.0] — 2026-11-07
### Adicionado
- **Assistente de sintonia** (age no VFO e no filtro, não no áudio):
  - **Auto-sintonia SSB**: estima o erro de sintonia pela estrutura harmônica da voz ao longo do tempo
    e corrige o VFO (erro típico abaixo de 15 Hz, em USB e LSB); modo contínuo opcional.
  - **Detectar modo**: identifica WFM, NFM, AM, CW e USB/LSB (a banda lateral é decidida pelos harmônicos
    da própria voz) e ajusta modo, filtro e sintonia.
  - **Ajustar filtro**: bordas do passband ajustadas à largura real do sinal.
- **Voltar no tempo**: buffer de 10–60 s da faixa inteira; reouça os últimos segundos de qualquer frequência,
  enquanto o waterfall segue ao vivo.
- **Receptores extras**: até 4 canais da mesma faixa ouvidos junto com o principal, com modo, volume
  e squelch próprios e marcadores verdes no waterfall.
- **Transcrição local opcional** das gravações por atividade (faster-whisper), com destaque dos indicativos.
- **Atualização automática** pelo www.pt2vhf.com: aviso de versão nova, download com conferência de
  tamanho e SHA-256 e instalação (instalador ou portátil).
- **Instalador e versão portátil para Windows** com autoteste (`--selftest`).

## [0.2.0] — 2026-11-07
### Adicionado
- **Memórias prontas**: pacotes importáveis com um clique — radioamador (chamada e fonia),
  modos digitais (FT8/FT4/WSPR), satélites/ISS, aviação (frequências gerais), marítimo VHF
  (canais simplex, DSC, AIS), PX 11 m (40 canais), rádio comunicador (FRS e PMR446) e sinais horários.
  Não duplica canais existentes; opção de marcar como favoritos.
- **Barra de favoritos** (teclas ★) acima do waterfall: um clique para escutar, botão "+ Favorito",
  destaque do canal em uso e remoção pelo menu de contexto.
- **Scanner por espectro** (painel *Scanner*):
  - varre faixas inteiras pelo FFT, por segmentos (~640 canais/s a 1,2 MS/s), ignorando o pico DC;
  - faixas prontas: aviação, marítimo, 2 m, 70 cm, VHF/UHF serviços, FRS, PMR446, PX,
    radiossondas, FM broadcast e ondas curtas (49/31/25/19 m);
  - modos **Só descobrir** e **Parar e escutar** (retomada após silêncio, tempo máximo no canal);
  - **canal prioritário** verificado periodicamente;
  - lista de frequências ativas com acessos, última vez, SNR, tempo ativo e memória correspondente;
  - bloquear frequências, salvar seleção como memórias, exportar CSV.
- **Gravação automática por atividade**: um WAV por transmissão enquanto o squelch está aberto,
  organizado por data, com lista para ouvir depois.

### Alterado
- A varredura de faixa do painel de memórias foi substituída pelo novo Scanner
  (a varredura de categorias de memória continua lá).
- Build do Windows passa a ser gerado apenas sob demanda.

### Corrigido
- Duas gravações iniciadas no mesmo segundo não sobrescrevem mais uma à outra.

## [0.1.0] — 2026-11-07
### Adicionado
- Primeira versão: display LCD estilo rádio, espectro + waterfall, modos NFM/WFM/AM/USB/LSB/CW/DSB/RAW,
  AGC, squelch, NB, NR, notch, equalizador de 8 bandas, gravação de áudio e IQ.
- Fontes: RTL-SDR, rtl_tcp, SoapySDR, arquivo WAV IQ e simulador.
- Memórias com categorias, plano de bandas, CSV do CHIRP, varredura de memórias, VFO A/B.
- Decodificadores APRS/AX.25 (posição, Mic-E, compactado, telemetria, clima, mensagens), DTMF e CTCSS.
