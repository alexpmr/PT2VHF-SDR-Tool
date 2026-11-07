# Changelog

Todas as mudanças relevantes do PT2VHF SDR Tool.

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
