# Changelog

Todas as mudanças relevantes do PT2VHF SDR Tool.

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
