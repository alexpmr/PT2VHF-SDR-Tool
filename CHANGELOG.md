# Changelog

## [1.0.9] — 2026-11-27 — favoritos, Auto contínuo e zoom de verdade no waterfall
### Favoritos
- A fileira de teclas de favoritos virou um menu suspenso compacto ao lado de "+ Favorito": ocupa uma linha só e comporta dezenas de entradas.
- Favoritos ordenados por frequência de uso (mais usados primeiro; empate pelo uso mais recente). Cada memória chamada conta um uso, salvo em `memories.json` (`use_count`, `last_used`); arquivos antigos continuam abrindo.
- Botão "−" e botão direito no menu removem o favorito selecionado.
### Waterfall
- Botão **Auto** virou liga/desliga: com ele ligado, piso e teto acompanham o sinal a cada segundo (acima de 800 MHz com FFT 32768 a tela não fica mais preta). Vem ligado por padrão; mexer em Piso/Teto desliga. Ctrl+L continua ajustando uma vez.
- **Zoom FFT:** com zoom alto (ex.: 10 kHz), o waterfall e o espectro passam a vir de um DDC da faixa visível (mistura, filtro FIR polifásico + Chebyshev II, decimação) com FFT própria de ~2048 bins na tela. Em 2,4 MS/s, 10 kHz de zoom passam de ~73 Hz/bin para ~3,7 Hz/bin; dois tons a 150 Hz aparecem separados. Rejeição de imagens ≥ 70 dB. Só roda enquanto o zoom está ativo (~5% de um núcleo em 2,4 MS/s).
### Decodificadores
- ACARS (131,550/131,725/131,825 MHz) e ADS-B (1090 MHz) já estão embarcados desde a v1.0.7; sem mudança de código nesta versão. Homologação com RF real continua pendente.

## [1.0.8] — 2026-11-27 — HF no RTL-SDR Blog V4/V4L
### RTL-SDR Blog V4 / V4 Lite (V4L)
- HF passa a ser recebido pelo conversor interno (upconverter) do V4 e do V4L com o driver RTL-SDR Blog. Antes, no V4L (sintonizador R820T) só era possível sintonizar HF ligando a amostragem direta, que desliga o sintonizador e deixava o waterfall só com ruído (PR #31).
- V4 e V4L são reconhecidos pelas strings USB ("Blog V4" / "Blog V4L"); faixa 0,5–1766 MHz com o driver Blog, independentemente do sintonizador.
- Amostragem direta é recusada nesses modelos, com aviso; configuração salva e troca automática HF/VHF não voltam a ligá-la.
- Aviso quando o V4/V4L abre com a biblioteca rtl-sdr padrão (sem HF); Diagnóstico mostra o produto USB.
- RTL-SDR Blog V3 e dongles genéricos inalterados (HF continua por amostragem direta, Ramo Q).
- Pendente: homologação com RF real no V4L.

## [1.0.7] — 2026-11-23 — decodificadores embarcados e splash do Sat Tool
### Splash
- Mesmo splash do Sat Tool: banner oficial PT2VHF (`pt2vhf/assets/branding/welcome-banner.jpg`) em camada não modal, embarcado no Setup e no Portable (PR #28).

### ADS-B, AIS e ACARS (mesmo SDR, um modo por vez)
- **ADS-B**: decodificador Mode S nativo (DF17/18, CRC-24 com correção de 1 bit, identificação, posição CPR global, altitude barométrica, velocidade). O app sintoniza 1090 MHz e, se preciso, reabre o SDR a 2,4 MS/s. Validado com vetores públicos de Mode S e IQ sintético.
- **AIS**: AIS-catcher v0.71 (GPL-3.0) embarcado. O IQ do SDR é reduzido a 288 kS/s em 162 MHz e servido por rtl_tcp local (127.0.0.1, porta efêmera); no Windows não se usa stdin porque o AIS-catcher lê `std::cin` em modo texto. Pacote oficial x64 com SHA-256 fixo, runtime MSVC app-local, licenças e fonte (git archive do commit) em `_internal/ais_catcher`.
- **ACARS**: decodificador nativo (AM, MSK 2400 bit/s, paridade ímpar, BCS CRC-16) das três frequências 131,550/131,725/131,825 MHz ao mesmo tempo; nova aba Decodificação > ACARS. Gerador sintético conferido pelo acarsdec; 6 de 7 blocos na gravação real de referência do acarsdec (`test.wav`).
- Abas ADS-B e AIS ganham "Receber pelo SDR"; importação de aircraft.json/NMEA externos continua disponível.
- Autoteste do executável inclui ADS-B e ACARS nativos e AIS-catcher sintético.
- Pendente: homologação com RF real (antena 1090 MHz, VHF marítimo e aeronáutico).

### RS41
- Setup e Portable Windows passam a incluir fsk_demod (codec2, LGPL-2.1) e rs41mod (rs1729/radiosonde_auto_rx, GPL-3.0), compilados no CI a partir de commit fixado, com textos de licença e código-fonte correspondente em `_internal/sonde_decoders`.
- Aba Sondas > Recepção RF usa automaticamente a cópia embarcada; caminho configurado pelo usuário tem prioridade e não cai silenciosamente para outra cópia; PATH fica como último recurso.
- Executáveis Windows forçam stdin/stdout binários (`packaging/sonde_win_binary_io.c`), evitando corrupção de IQ em pipes.
- Autoteste do executável roda um quadro RS41 **sintético** (CRC e Reed-Solomon válidos) por IQ -> fsk_demod -> rs41mod -> JSON. Não substitui captura IQ real de sonda: homologação RF continua pendente.

## [1.0.6] — 2026-11-22
- Waterfall preserva os bins nativos da FFT (até 32.768) em histórico limitado a 400 linhas; zoom estreito não perde resolução (#24).
- Zoom-out manual limitado à largura de banda IQ realmente amostrada (#23).
- Botão sempre visível para ocultar/mostrar o painel de áudio/DSP (Ctrl+Shift+A), com preferência salva.

## [1.0.5] — 2026-11-19
- Consolidação de todos os recursos aprovados da v1.0.4, sem reescrever DSP, drivers ou OTA.
- Testes de contrato da release (`tests/test_v105_stable_contract.py`).

## [1.0.4] — 2026-11-16
- Teste seguro do auxiliar OTA em Configurações e Ajuda (`-ProbeOnly`, sem instalar).
- Verificação dos pré-requisitos RS41 (fsk_demod/rs41mod) com diagnóstico copiável; diagnóstico dos backends SDRplay/Mirics.
- Campos de formulário compactos em telas grandes.

## [1.0.3] — 2026-11-15
- Corrige o erro "PowerShell exited before update" no OTA do Windows (lançador CREATE_NO_WINDOW com saída redirecionada) e grava `%TEMP%/PT2VHF-SDR-Tool-ota-launch.log`.
- Instalação manual única da v1.0.3 necessária para quem está em versão anterior.

## [1.0.2] — 2026-11-15
- Detecção e seleção separadas de SDRplay API (SoapySDRPlay3) e Mirics (SoapyMiri); módulos e drivers USB não incluídos (experimental).

## [1.0.1] — 2026-11-15
- Checkbox do upconverter permite alterar habilitação e offset durante a recepção, com reinício controlado do SDR.

## [1.0.0] — 2026-11-14
- Correção de VHF/UHF no RTL R820T (direct sampling), offset para upconverter externo de 100 MHz, melhorias de LCD, checkbox, recursos e OTA.

## [0.13.3] — 2026-11-11
### Manutenção OTA
- Quando o manifesto anuncia versão nova, mas o pacote é rejeitado, o aplicativo não abre o navegador automaticamente e explica o problema (URL, tipo, tamanho ou SHA-256).
- O fluxo válido continua baixando dentro do aplicativo e verifica tamanho e SHA-256 antes de executar o helper; nenhuma restrição de integridade foi reduzida.
- Testes Qt de regressão para a detecção com pacote ausente e prevenção de abertura de navegador.
- Nota de migração: clientes v0.13.0 precisam de atualização manual única para v0.13.1 ou superior, pois a validação de URL incorreta já está compilada nos binários antigos.
### Waterfall
- Duplo clique na imagem do waterfall sintoniza o ponto RF selecionado e centraliza o VFO sem alterar o nível atual de zoom; o clique simples continua sintonizando e o duplo clique no espectro continua restaurando o zoom total.
- Restrições de IQ disponível, capacidade do SDR e testes Qt de gesto nativo, pan e seleção inválida; QA cruzado Windows/Linux obrigatório.
### Status
- Publicada no GitHub em 11/11/2026. IA IQ/ONNX continua fora da release.

## [0.13.2] — 2026-11-11
### Implementado no código (branch release/stable-v0.13.2)
- Sintonia no waterfall/espectro respeita os limites da largura IQ realmente adquirida, mesmo com zoom ou pan fora da faixa; mantém arredondamento por passo e associação com o VFO.
- Arrastar o passband para uma região não adquirida deixa o VFO original inalterado e restaura o marcador.
- Duplo clique fora das áreas de espectro não interfere no zoom.
### Testes e distribuição
- Novos testes Qt sintéticos de cena→RF, limites de IQ, ausência de sinal, passband e limites de arredondamento. **Aprovação do CI Windows e publicação ainda pendentes.**
- IA neural IQ/ONNX continua isolada no PR #2; RS41, S-meter absoluto e qualidade RF real não foram homologados.
- A sincronização do site oficial com a release GitHub foi registrada como bloqueio externo na issue PT2VHF-Site #18.

## [0.13.1] — 2026-11-11
- Manutenção estável publicada no GitHub (detalhes nas notas `docs/RELEASE_NOTES_0.13.1.md`).

## [0.13.0] — 2026-11-09
### Implementado no código
- Ajuste manual do tamanho do LCD em Configurações → Display (50–150%), mantendo proporção de frequência, S-meter, indicadores e teclas; preferência persistida no JSON do usuário.
- Matriz LCD compactada para mostrar somente bandas confirmadas como suportadas pelo SDR atual; mudança de fonte/dispositivo/recepção direta atualiza visibilidade, sem apagar preferências.
- Fontes rtl_tcp e SoapySDR verificam alcance informado pelo receptor; arquivo IQ não sintonizável restringe frequências à largura gravada.
- Reorganização da interface: Decodificação (ADS-B, Sondas, AIS e APRS/DTMF/CTCSS), Ferramentas (Transcrição/Legendas), popup de legendas com apenas texto e remoção da aba principal Satélites.
### Testes, homologação e publicação
- Regressões Linux/Qt de navegação, escala, ocultação de bandas e texto do popup. Ainda pendem testes visuais no Windows, SDR físico, carga de CPU e validação de fala real.
- Radiossondas RS41 continuam sem homologação RF; ADS-B/AIS nativos, SSTV, fonia digital, tradução e demais itens do backlog não estão implementados.
- Versão somente publicada quando os builds Windows Setup/Portable, SHA-256 e verificação do site/OTA estiverem concluídos.

Todas as mudanças relevantes do PT2VHF SDR Tool.

## [0.12.0] — 2026-11-08
### Implementado no código
- Redução neural RNNoise real para fonia a 48 kHz, mix de intensidade, worker assíncrono com fila limitada e fallback seguro. Dados RF/decoder continuam originais.
- Perfil Sinal fraco combina NB/NR/AGC com RNNoise quando disponível e em modo voz.
- Backend faster-whisper/CTranslate2 no empacotamento; download explícito de modelos tiny/base/small, transcrição local ao vivo e de WAV do Scanner, idioma e CSV.
- Mensagens de dependência/erro e autotestes de runtime dos executáveis.
### Homologação / limites
- Qualidade subjetiva, latência, desempenho de CPU e precisão de indicativos requerem teste com SDR real.
- Pesos Whisper baixados pelo usuário na primeira instalação; não há download automático em segundo plano nem envio de áudio para serviços externos.
- Tradução automática, IA em IQ, CW, SSTV, voz digital e vários decodificadores continuam no backlog.

## [0.11.0] — 2026-11-08
### Implementado no código
- LCD vetorial redimensionado proporcionalmente em telas/janelas menores, sem podar a frequência ou as teclas; mapeamento de clique e rolagem convertido de pixels para coordenadas lógicas.
- Bandas em grade de 5 colunas na área superior direita do display, acima do S-meter, com tema, destaque e disponibilidade.
- S-meter agora distingue ausência de dados IQ (sem barras) de leitura real, com atualização de amostras, estados e tooltip de dBFS/dBm aproximado/S. Função determinística de mapeamento do nível para 40 segmentos.
- RS41: IQ recentrado em 0 Hz, combinando com filtro e máscara do fsk_demod -5/+5 kHz; antes havia portadora +12 kHz com máscara ±5 kHz, combinação incompatível.
- Testes novos de escala do LCD, hitboxes, 5 colunas, sinal variável e RS41 em banda-base.
### Homologação e pendências
- Os testes de software e build não comprovam o funcionamento da decodificação RS41 real; binários externos fsk_demod/rs41mod e amostra RF validada ainda são necessários.
- Os recursos avançados do backlog (IA neural, SSTV, voz digital, idiomas integrais, vários demoduladores RF) não estão concluídos.
- Publicação no site/OTA é independente da release do GitHub.

## [0.10.0] — 2026-11-08
### Implementado
- Eliminada aba principal genérica Decodificadores; APRS/DTMF/CTCSS movidos para o Scanner. ADS-B, AIS e Sondas Meteorológicas agora são painéis principais separados.
- Removida a interface APRS iGate RX e seu acionamento; nenhum envio APRS-IS pelo receptor.
- Teclas de seleção de bandas integradas dentro do LCD, preservando temas, botões de modos e desabilitação visual para frequências não suportadas.
- Diagnóstico RS41: métricas de IQ, JSON, quadros sem GPS, perdas, erro dos subprocessos, captura de IQ para diagnóstico, estatísticas FSK e informações sobre dependências ausentes.
- Adicionada recuperação de quadros RS41 que chegam sem coordenadas; correção de flags do decodificador conforme radiosonde_auto_rx.
- Rastros por estação no mapa OSM e exportação GPX/KML com escape seguro dos campos; CSV permanece.
- Testes de compatibilidade e documentação de limitações.
### Pendências / restrições
- RS41 continua sem homologação com transmissão RF real; necessita fsk_demod e rs41mod externos. DFM/M10/M20/RS92 continuam pendentes.
- Internacionalização integral, IA neural, SSTV, voz digital e demodulação nativa ADS-B/AIS permanecem no backlog.
- A publicação no site oficial e a atualização OTA são verificadas separadamente da release GitHub.

## [0.9.0] — 2026-11-08
### Implementado em código
- IQ ao vivo do SDR compartilhado com pipeline RS41: translação para +12 kHz e decimação a 48 kS/s, uso de fsk_demod + rs41mod externos, com fila limitada e telemetria em tabela/mapa.
- Previsão SGP4 de passagens e ajuste RX Doppler com TLE importado.
- APRS iGate somente RX desativado por padrão, com autenticação APRS-IS, qAO e bloqueio de retransmissões indevidas.
- Menu de idiomas e bandeiras com catálogo parcial de traduções para PT, EN, ES, FR, DE, IT e ZH.
- Testes de DSP IQ, formato de comandos, filtros APRS e órbitas.
### Limites e não implementados
- Os programas externos fsk_demod/rs41mod não acompanham Setup/Portable e não há validação RF com uma sonda real. Somente RS41; demais protocolos pendentes.
- Internacionalização parcial, sem tradução de fonia. Sem IA neural, SSTV, voz digital, ADS-B/AIS DSP nativo, NOAA APT/Meteor LRPT, RDS, ACARS, pagers e KiwiSDR.
- Site oficial/OTA requerem publicação separada e conferência pública.

## [0.8.0] — 2026-11-08
### Implementado no código
- Integração ADS-B com arquivos aircraft.json de readsb/dump1090: posições, ICAO, callsign, altitude, velocidade e rumo. Requer demodulador externo.
- Decodificação local de mensagens NMEA AIS (tipos 1/2/3/18/19 de posição e tipo 5 para nome) produzidas por AIS-catcher/rtl_ais. Requer captura externa de RF.
- Importação de telemetria de radiossondas em JSON local, com dados meteorológicos e fase de subida/descida; sem decodificação RS41 nativa ou previsão de queda.
- Abas de tráfego com fontes configuráveis, atualização periódica, tabelas, CSV e mapa unificado OSM.
- CAT Hamlib rigctld: ler frequência/modo e acompanhar o rádio, e enviar a sintonia do SDR manualmente, sem PTT.
- Banco de memórias por região/cidade, com troca confirmada e importação CHIRP CSV isolada por perfil.
- Formulários de configurações mais compactos; testes determinísticos de ingestão AIS/ADS-B/sondas, CAT e regiões.
### Não implementado
- IA neural offline, tradução/localização integral, SSTV, DMR/D-STAR/C4FM com áudio, ADS-B ou AIS por DSP nativo, decodificação RS41 IQ, Doppler/órbitas, WFM RDS, ACARS e demais itens de pesquisa.

## [0.7.0] — 2026-11-08
### Implementado
- Dois medidores analógicos vetoriais com ponteiros suavizados: S-meter calibrado em dBm / S-units e VU do áudio em dBFS.
- Três estilos de instrumento com exemplos em Configurações → Display: Valvulado, Militar e Estúdio.
- Histórico persistente de detecções do scanner em janela móvel de 24 horas; mapa de calor por frequência (12,5 kHz) e hora, com CSV. Não é medida contínua de ocupação.
- Mapa APRS local com estações recebidas e rastros de posição, aberto no navegador sobre tiles OSM, sem envio ao APRS-IS.
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
