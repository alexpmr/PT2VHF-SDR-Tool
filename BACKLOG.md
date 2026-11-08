# Backlog — PT2VHF SDR Tool

Itens registrados pelo mantenedor. Não implementar até o pedido de versão nova.

## Pendentes

### Recursos sugeridos ainda não implementados (registrado em 08/11/2026)
Registrados "de acordo com as sugestões" dadas ao mantenedor (resposta "O que mais um programa de SDR de 0–2 GHz
deveria ter" e roteiro do README). Implementar conforme viabilidade; a ordem pode ser decidida no pedido de versão.
- **Decodificadores para escutas:**
  - **ADS-B** (aviões no mapa, 1090 MHz) e **AIS** (navios no mapa, 161,975/162,025 MHz);
  - **ACARS** (mensagens de aeronaves, ~131 MHz);
  - **POCSAG/FLEX** (pagers);
  - **imagens de satélites meteorológicos** NOAA APT e Meteor LRPT, com **previsão de passagens**;
  - voz digital (DMR, D-STAR, YSF): só após avaliar as questões de patente/licença do codec AMBE.
- **Mapa APRS** (estações recebidas, rastros e objetos) e **iGate somente RX** (envio ao APRS-IS, opcional).
- **WFM estéreo e RDS** (nome da emissora, texto e música).
- **Mapa de atividade em 24 h**: em que horários cada frequência/faixa fica ocupada (a partir do scanner).
- **Banco de memórias por região**: escolher cidade/região e carregar o que se ouve ali (repetidoras, aviação por
  aeroporto, rádios FM/AM locais), aproveitando bases públicas exportáveis em CSV do CHIRP.
- **Limpeza de ruído com IA no áudio** (ex.: RNNoise/DeepFilterNet), opcional, além da redução de ruído atual.
- **Satélites**: previsão de passagens e **correção Doppler** automática na sintonia.
- **Controle CAT (Hamlib)** para sincronizar frequência/modo com o rádio.
- **Cliente para receptores KiwiSDR remotos** (usar um KiwiSDR da internet como fonte de sinal).

### Decodificador de radiossondas meteorológicas (RS41 e outras) com mapa e previsão de trajetória (registrado em 07/11/2026)
- Decodificar sondas meteorológicas na faixa de 400–406 MHz (e 1680 MHz quando o hardware permitir):
  **Vaisala RS41** (prioridade) e outras comuns, ex.: RS92, Graw DFM-06/09/17, Meteomodem M10/M20,
  Intermet iMet-4, Meisei, LMS6 — conforme viabilidade.
- **Informações em tempo real, de forma amigável**: tudo o que a sonda transmitir, como número de série/ID,
  frequência, posição (lat/lon), altitude, velocidade vertical (subida/descida) e horizontal, rumo,
  temperatura, umidade, pressão, ponto de orvalho, bateria, quadro/contador, satélites GPS, tempo de voo,
  fase (subida, estouro do balão, descida) e qualidade da recepção; unidades claras e gráficos simples
  (altitude, temperatura e umidade × tempo).
- **Mapa** com a posição atual, o rastro percorrido, a sua estação (locator) e distância/azimute até a sonda.
- **Previsão de trajetória e do ponto de queda** (subida até o estouro e descida), atualizada durante o voo,
  com estimativa de horário e local de pouso — para quem gosta de buscar sondas.
- Detectar e sintonizar sondas automaticamente (ex.: scanner na faixa de radiossondas), aviso ao surgir uma
  nova, histórico de sondas recebidas e exportação (CSV/KML/GPX).
- Verificar viabilidade e licença de reaproveitar decodificadores e serviços abertos (ex.: projetos tipo
  radiosonde_auto_rx/RS1729, previsores de trajetória como o Tawhiri/SondeHub) antes de implementar;
  envio opcional dos dados ao SondeHub.
- Mostrar também na interface web (mapa e dados da sonda no navegador).

### Campos de configuração com a largura do conteúdo, não da página inteira (registrado em 07/11/2026)
- Hoje, nas abas de configuração (Configurações → Receptor, Modo / Filtro, Geral · Web · Atualizações e demais
  ajustes), as listas suspensas e campos se esticam por toda a largura da janela — ex.: **Fonte**, **Dispositivo**,
  Amostragem, Nível da interface, Tema, Biblioteca do RTL-SDR.
- Pedido: cada menu/campo com a largura suficiente para o texto que mostra (o item mais longo da lista), sem ocupar
  a largura toda da página; rótulo e campo alinhados à esquerda, como nos demais programas PT2VHF.
- Vale para **todas** as opções de configurações e ajustes (incluindo os painéis Áudio / DSP, Scanner,
  Decodificadores e Receptores extras quando tiverem o mesmo problema); conferir também em janela maximizada e
  com o painel estreito (sem cortar texto nem criar rolagem horizontal).

## Concluídos
- 0.5.0 — itens registrados em 07/11/2026: RTL-SDR voltou a abrir (dithering -1 + LIBUSB_ERROR_ACCESS da 0.4.1);
  abas superiores (Receptor, Memórias/Varredura, Scanner, Decodificadores, Receptores extras, Configurações com
  sub-abas Receptor e Modo/Filtro) sem botões de modo duplicados; indicador de versão/atualização no topo;
  interface web pelo IP sem chave (somente rede privada, chave opcional); lembrar o receptor ligado e reconectar ao
  abrir; modo apresentação (F11).
- 0.4.1 — 0.4.0 não abria o RTL-SDR (LIBUSB_ERROR_ACCESS): recurso automático para a biblioteca padrão (a da 0.3.0),
  opção de biblioteca em Configurações, espera do fechamento antes de reabrir e erro com diagnóstico do driver.
- 0.4.0 — todos os itens registrados em 07/11/2026: travamento ao mudar de banda (V4) com recuperação automática e
  driver RTL-SDR Blog; auto-sintonizar; modo AUTO; transmissão vizinha ◀▶; modos no display; três níveis de
  interface; waterfall arrastável; painel de áudio sem rolagem; VOX; Configurações + interface web com áudio;
  anúncio ao abrir; OTA e instalador no padrão dos demais programas.
- 0.3.0 — IA/assistente para SSB (auto-sintonia pelos harmônicos da voz, detecção de modo e banda lateral,
  filtro adaptativo, transcrição local opcional), voltar no tempo, receptores extras, instalador/portátil
  Windows e atualização automática pelo www.pt2vhf.com.
- 0.2.0 — memórias prontas, favoritos, scanner por espectro e gravação por atividade.
- 0.1.0 — primeira versão.
