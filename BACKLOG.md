# Backlog — PT2VHF SDR Tool

Itens registrados pelo mantenedor. Não implementar até o pedido de versão nova.

## Pendentes

### Teclas de banda no display (um botão por banda) (registrado em 08/11/2026)
- Hoje a banda só se escolhe na lista "Bandas" em Configurações → Modo / Filtro.
- Colocar no **display** uma fileira de teclas de banda, como num transceptor: **160, 80, 60, 40, 30, 20, 17, 15,
  12, 10, 6, 2 m, 70 cm** (e outras faixas úteis para escuta, ex.: PX/11 m, FM broadcast, aviação, marítimo),
  um clique por banda.
- Ao clicar, ir para a banda com o modo adequado (LSB abaixo de 10 MHz, USB acima, FM em VHF/UHF, conforme o plano
  de bandas) e **lembrar a última frequência/modo usados em cada banda** (band stacking), voltando nela no
  próximo clique; segundo clique na mesma banda pode alternar entre posições salvas (CW / SSB / digital).
- Destacar a banda atual; desabilitar/avisar bandas fora do alcance do dispositivo (ex.: HF no RTL-SDR sem
  amostragem direta ou V4).
- Escolher em Configurações quais bandas aparecem (radioamador, escuta ou personalizadas) e respeitar os níveis
  de interface e o modo apresentação; caber sem rolagem (quebra em duas linhas ou "mais…").

### Botão "Centralizar" no waterfall (registrado em 08/11/2026)
- Botão na barra do waterfall (e atalho de teclado) que **centraliza a visão no cursor/VFO**: traz a frequência
  sintonizada para o meio do espectro/waterfall, mantendo o zoom atual (útil depois de arrastar ou dar zoom).
- Se o VFO estiver fora da faixa recebida, recentralizar também o receptor nele.
- Opção "manter centralizado" (acompanhar o VFO ao sintonizar), desligada por padrão.

### Padrões da primeira execução: SDR físico, configuração do SDR e interface Avançada (registrado em 08/11/2026)
- **Fonte padrão = SDR físico (RTL-SDR)**, não o Simulador. O Simulador continua disponível na lista, só deixa de
  ser o padrão.
- **Ao abrir sem o SDR configurado** (primeira execução ou nenhuma fonte física configurada/salva), levar o
  usuário direto para **Configurações → Receptor**, com uma mensagem curta explicando o que escolher (fonte,
  dispositivo, taxa) e o botão Ligar; procurar dispositivos automaticamente e, se não houver nenhum, oferecer
  Preparar RTL-SDR (driver WinUSB) e Diagnóstico. Considerar configurado depois do primeiro Ligar com sucesso.
- **Nível de interface padrão = Avançado** (hoje é Intermediário) para novas instalações; quem já escolheu um
  nível mantém o seu.
- Combinar com o item já entregue "reconectar ao abrir" (0.5.0): uma vez configurado, as aberturas seguintes
  reconectam o SDR físico normalmente.

### Novos painéis analógicos com VU meter / S-meter de ponteiro (registrado em 08/11/2026)
- Além do display LCD atual, oferecer **painéis no estilo analógico**, simulando rádios clássicos: instrumentos com
  **ponteiro** (agulha) e escala iluminada.
- Instrumentos: **S-meter** (S1…S9+60, dBm), **VU meter** do áudio (nível de saída, com escala em dB e zona
  vermelha), e opcionalmente medidores de SNR/desvio (FM) e nível do squelch; movimento realista da agulha
  (inércia, subida rápida e retorno suave, retenção de pico opcional).
- Mostrador de frequência analógico/vintage (ex.: dial com escala deslizante ou "nixie"), mantendo a leitura
  digital precisa e as teclas de modo clicáveis.
- Vários estilos para escolher (ex.: rádio valvulado âmbar, receptor militar/profissional, VU de estúdio),
  com **exemplo de cada um para escolher** em Configurações → Display (mesmo seletor do item de temas do display).
- Escalável e nítido em qualquer tamanho (desenho vetorial), leve na CPU, funcionando também no modo apresentação
  e, se possível, na interface web.

### Idioma do programa com bandeiras, como nos demais programas PT2VHF (registrado em 08/11/2026)
- Hoje o SDR Tool só existe em português.
- Escolha do idioma da interface num **menu suspenso (pull-down) com a bandeira de cada país** ao lado do nome
  nativo do idioma, no mesmo padrão dos demais programas PT2VHF e do site (pt-BR, en, es, fr, de, it, zh);
  em Configurações e acessível também pelo cabeçalho; aplica na hora (ou após reiniciar, com aviso) e fica salvo.
- Traduzir toda a interface (abas, menus, painéis, mensagens, dicas, diálogos de atualização e anúncio de abertura).
- Esse idioma é o **idioma padrão** usado pela transcrição/tradução da fonia.
- Conferir o seletor e as bandeiras dos outros programas PT2VHF/site antes de implementar, para ficar idêntico.

### Tratamento com IA para melhorar sinais fracos (débeis) (registrado em 08/11/2026)
- Objetivo: tornar inteligível a fonia (e melhorar sinais de CW/dados) que chega fraca, perto do ruído.
  Amplia o subitem "Limpeza de ruído com IA no áudio" de "Recursos sugeridos".
- **Áudio (voz):** redução de ruído por rede neural treinada para voz (ex.: RNNoise, DeepFilterNet ou similar),
  removendo chiado, estática e QRM sem o som "metálico" da subtração espectral atual; intensidade ajustável e
  comparação liga/desliga em tempo real.
- **Antes da demodulação (IQ):** filtro adaptativo que segue o sinal (largura e centro do passband automáticos),
  supressão de interferências estreitas (portadoras/batimentos) e de ruído impulsivo por IA, e AGC que não
  "bombeia" com o ruído.
- **CW:** realce do tom e filtro estreito automático; opção de decodificar CW fraco para texto.
- **Indicador** de melhoria (SNR estimado antes/depois) e um botão único "Sinal fraco" que liga o conjunto
  adequado ao modo atual.
- Funcionar **localmente, sem internet**, sem travar a recepção (segundo plano, baixa latência) e combinável com a
  transcrição em tempo real; avaliar CPU/GPU, tamanho do pacote e licenças dos modelos antes de implementar.

### Transcrição de voz em tempo real, em todos os modos (registrado em 08/11/2026)
- **Acréscimo (08/11/2026):** o texto pode sair **no idioma original** da fonia ou **traduzido para o idioma
  padrão escolhido pelo usuário** (o idioma do programa); opção em Configurações e alternância rápida na legenda
  (original × traduzido), mantendo o original no histórico/exportação. Tradução local, sem internet.
- Hoje existe só a transcrição local **opcional e depois da gravação** (coluna do Scanner, gravações por atividade,
  requer `pip install faster-whisper`).
- Pedido: transcrever **em tempo real** a fonia da transmissão que está sendo ouvida, em **todos os modos de voz**
  (NFM, WFM, AM, USB, LSB, DSB e, quando houver, voz digital), para facilitar o entendimento.
- Mostrar o texto ao vivo numa área legível (legenda sob o display/waterfall e painel com histórico), com horário,
  frequência e modo de cada trecho; separar por transmissão (squelch/VOX); destacar indicativos reconhecidos.
- Idioma automático ou escolhido (pt/en/es…); funcionar **localmente, sem internet**, já incluído no instalador
  (sem exigir pip), com escolha de modelo (rápido × preciso) e uso de GPU quando houver; não pode travar a
  recepção nem o áudio (processamento em segundo plano, latência de poucos segundos).
- Também na interface web e no modo apresentação (legenda); salvar/exportar o texto (TXT/CSV) junto com as
  gravações; ligar/desligar por botão e em Configurações.
- Avaliar o tamanho do pacote e o desempenho em PCs modestos antes de implementar (ex.: modelo baixado sob
  demanda pelo www.pt2vhf.com).

### Decodificadores: ADS-B, AIS, DMR, D-STAR, C4FM e SSTV da ISS (registrado em 08/11/2026)
- Pedido explícito do mantenedor (reforça e prioriza parte do item "Recursos sugeridos"):
  - **ADS-B** (1090 MHz): aviões no mapa com indicativo, altitude, velocidade, rumo e rastro; tabela de aeronaves.
  - **AIS** (161,975 / 162,025 MHz): navios no mapa com nome, MMSI, tipo, rumo e velocidade; tabela de embarcações.
  - **Voz digital DMR, D-STAR e C4FM (YSF)**: decodificar e mostrar os metadados (ID/indicativo, talkgroup,
    slot, mensagens, GPS quando houver) e, se possível, o áudio; o codec AMBE/IMBE tem questões de patente —
    avaliar opções legais (ex.: decodificação de áudio opcional por componente externo instalado pelo usuário)
    antes de implementar.
  - **SSTV da ISS** (145,800 MHz, eventos ARISS): receber e montar as imagens automaticamente (modos PD120,
    PD180, Robot36, Martin, Scottie…), com galeria das imagens recebidas, data/hora e salvamento; aviso de
    passagem da ISS e correção Doppler quando houver.
- Mostrar as informações de forma amigável e, quando houver posição, no mapa (o mesmo das radiossondas/APRS).

### Configuração do display na aba Configurações → Display, com exemplos para escolher (registrado em 08/11/2026)
- Hoje o tema do display aparece em dois lugares: "Display:" na barra do waterfall e "Tema do display" em
  Configurações → Geral.
- Mover a configuração do display para uma sub-aba própria **Configurações → Display** (tirar da barra do waterfall).
- Mostrar **um exemplo de cada tema** (Âmbar, Verde, Azul (negativo), Noturno, Branco e os que vierem) como
  miniatura do display real (frequência, S-meter, indicadores), para escolher clicando no exemplo; o selecionado
  fica destacado e aplica na hora.
- Reunir ali os demais ajustes visuais do display, se houver (ex.: relógio local/UTC, calibração do S-meter).

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
