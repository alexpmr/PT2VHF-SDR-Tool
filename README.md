# PT2VHF SDR Tool

Receptor SDR para radioamadores com **interface de painel de rádio** (display LCD de 7 segmentos,
S-meter, VFO A/B, memórias) e **waterfall** no estilo KiwiSDR / SDR# / SDR++.
Funciona com **RTL-SDR**, servidores **rtl_tcp**, qualquer rádio suportado pelo **SoapySDR**
(Airspy, HackRF, SDRplay, LimeSDR…), **gravações IQ em WAV** e um **simulador** de banda embutido
(para testar sem hardware).

Plataforma inicial: **Windows** (também roda em Linux/macOS).

![Scanner por espectro e teclas de favoritos](docs/screenshot-scanner.png)
![Tela principal com decodificação APRS](docs/screenshot-aprs.png)
![Tema azul, DTMF e CTCSS](docs/screenshot-azul.png)

## Recursos

### v0.12.0 — IA neural e transcrição de voz offline
- **RNNoise (rede neural real):** redução neural de ruído de voz em NFM/AM/USB/LSB/DSB, com botão no painel de áudio e mistura áudio seco/tratado de 0 a 100%. O modelo RNN vem no backend pyrnnoise (licença Apache-2.0), incluído nos binários.
- **Recepção sem bloqueios:** inferência em thread separada com fila limitada para manter o SDR responsivo. Sob sobrecarga de CPU, áudio antigo pode ser descartado. IQ, waterfall, S-meter, APRS/DTMF/CTCSS, CW/RAW e gravações IQ não passam pelo denoiser. WFM é preservado para evitar prejudicar música. Áudio tratado alimenta saída, web, gravação contínua e legendas; gravação de atividade permanece original.
- **Perfil Sinal fraco · IA + DSP:** combina NB/NR/AGC com RNNoise nos modos de voz, caso disponível; restaura as configurações anteriores.
- **Transcrição local:** faster-whisper/CTranslate2 incluídos no programa, reconhecimento ao vivo em blocos de aproximadamente 4 segundos (não palavra a palavra), com frequência, modo, idioma, indicativos, histórico e CSV; WAV gravado pelo Scanner também pode ser transcrito.
- **Primeiro uso no código em desenvolvimento:** Ferramentas → Transcrição → escolha tiny/base/small → Baixar modelo → Ativar legendas em tempo real. Um popup sobre o receptor exibe apenas o texto reconhecido. Em Ferramentas → Legendas ao vivo fica o histórico com CSV. O download inicial exige Internet uma vez; o modelo é salvo em AppData/PT2VHF-SDR-Tool/models/whisper-tiny (ou equivalente) e o áudio não é transmitido à rede. **A versão instalada v0.12.0 ainda usa Scanner → Legendas ao vivo** até que um novo instalador seja publicado.
- **Limitações:** RNNoise trata fonia, não recupera pacotes ausentes, e pode distorcer SSB extremamente fraco. Whisper pode errar indicativos/números. Os pesos Whisper não são distribuídos no instalador. IA sobre IQ, tradução automática, CW e voz digital permanecem pendentes.


### Novo na v0.11.0 — LCD responsivo, S-meter e RS41
- **S-meter:** a ausência de amostras IQ recentes agora mostra "S-- / -- dBm" e nenhuma barra acesa; leituras válidas atualizam os segmentos proporcionalmente, com retenção de pico. O tooltip do LCD mostra os valores de entrada em dBFS, dBm aproximado e unidade S. Calibração absoluta em dBm requer comparação com referência.
- **LCD:** painel de 1.100 × 255 unidades lógicas, renderizado vetorialmente com escala uniforme (letterboxing, sem cortes); ajuste proporcional de frequências, etiquetas, S-meter e teclas. A posição clicada é convertida às coordenadas lógicas, inclusive em janelas estreitas.
- **Bandas:** matriz compacta de cinco colunas no lado direito do LCD, acima do S-meter, com aparência e destaque harmonizados com as teclas de modo e estado desabilitado para faixas não suportadas. Não existe mais grade sob as teclas de modo.
- **RS41:** corrigida uma incompatibilidade entre a sintonia IQ antiga em +12 kHz e a máscara FSK moderna de ±5 kHz. A cadeia agora converte o IQ para banda-base (0 Hz) e utiliza a janela -5/+5 kHz adotada pelo radiosonde_auto_rx mais recente. Ainda requer binários externos e validação com sonda real; não declarar homologado.
- **Testes:** verificações de geometria/redimensionamento, mapa de cliques após escala, seleção de tema, variação de barras sem sinal e com diferentes níveis, além da conversão IQ para 0 Hz.

**Escopo:** esta versão corrige falhas prioritárias verificáveis. Não implementa integralmente o extenso backlog de IA neural, voz digital, SSTV, demodulação ADS-B/AIS nativa, NOAA/Meteor e idiomas completos.


### Novo na v0.10.0 — navegação, LCD, RF e rastros
- **Interface**: abas principais ADS-B, AIS e Sondas Meteorológicas independentes; painel APRS/DTMF/CTCSS reunido no Scanner; iGate APRS-IS removido da navegação e sem envios.
- **Sondas meteorológicas**: recepção RS41 e importação JSON na mesma área; medidores de blocos IQ, quadros JSON, quadros sem GPS, posições, perdas, estados dos processos e mensagens de erro de fsk_demod/rs41mod; gravação manual e limitada a 20 segundos de IQ complexo 48 kS/s (.c16) para diagnóstico.
- **Atenção**: a existência de IQ ou sinal no waterfall não comprova decodificação. A recepção RS41 real ainda depende dos binários externos fsk_demod/rs41mod e continua sem validação de campo; novos testes de bancada necessários.
- **LCD**: as teclas de seleção de bandas agora estão dentro do painel LCD (junto das teclas de modos), mantendo cores e estados por tema; fontes menores/esmaecidas para bandas não suportadas.
- **Tráfego e sondas**: mapas OSM exibem rastros por estação, histórico de posições limitado a 5 mil pontos e exportação GPX/KML, além de CSV. ADS-B e AIS mantêm ingestão por software de decodificação externo.
- **Testes**: regressões dos módulos de tela, relatórios de diagnóstico e de formato GPX/KML.


### Novo na v0.9.0 — RS41 por IQ, órbitas e APRS iGate
- RS41 diretamente do IQ do SDR: aba Decodificadores > RS41 IQ ao vivo, 400–406 MHz. A aplicação reutiliza a captura atual, converte para IQ complex int16 em 48 kS/s e conecta os programas externos fsk_demod e rs41mod (radiosonde_auto_rx). Os executáveis não são incluídos na distribuição; sem eles, a decodificação não funciona.
- Satélites: TLE/SGP4 com previsão de passagens, azimute, elevação e correção Doppler opcional em recepção. Dependência sgp4 incluída; requer TLE do usuário. Não controla rotor ou PTT.
- APRS iGate somente RX: habilitação explícita, indicativo e passcode pessoal, envio RF -> APRS-IS qAO; não envia pacotes à rede RF.
- Menu de idiomas e bandeiras PT/EN/ES/FR/DE/IT/ZH, com tradução de abas e controles essenciais. Demais mensagens permanecem em português; tradução integral pendente.
- Diagnóstico de sonda: verifique modelo RS41, instalação dos dois decodificadores, frequência, SNR e sinais válidos. A existência de RF no waterfall não equivale a dados decodificados. DFM, M10/M20, RS92 e outros modelos seguem pendentes.

### Novo na v0.8.0 — tráfego externo, mapas e CAT
- **ADS-B (1090 MHz):** importa o arquivo `aircraft.json` de `readsb` ou `dump1090`, com indicativo, posição, altitude, velocidade e rumo. **Exige decodificador externo**; não demodula ADS-B em IQ dentro do SDR Tool.
- **AIS (161,975/162,025 MHz):** lê arquivos NMEA `!AIVDM` de `AIS-catcher`/`rtl_ais` e decodifica mensagens de posição classe A/B (1, 2, 3, 18, 19) e identificação tipo 5, incluindo MMSI, posição, velocidade e rumo.
- **Radiossondas:** acompanha JSON local produzido por `radiosonde_auto_rx` ou conversor, mostrando ID, posição, altura, velocidade vertical e dados meteorológicos quando presentes. Não decodifica RS41 diretamente no SDR Tool nem prevê automaticamente a queda.
- **Mapa conjunto:** posições em mapa OSM/Leaflet gerado localmente, com exportação CSV por fonte. Os tiles exigem Internet; nenhum envio automático para servidores externos.
- **CAT via Hamlib:** `rigctld` TCP, consulta frequência e modo por demanda ou sincronização de leitura; envio manual de sintonia/modo para o rádio. **Sem PTT**. Requer Hamlib externo configurado.
- **Perfis por região:** salve os canais da cidade/região atual, carregue outro banco e importe diretamente CSV CHIRP como região independente.
- **Ajustes compactos** em Configurações e no painel Receptor.
- A v0.8.0 **não inclui ainda** IA neural, tradução integral, decodificação DMR/D-STAR/C4FM, SSTV, RS41 em IQ, previsão de satélites ou modelos de fala embarcados.


### Display de rádio (LCD)
- Frequência em dígitos de 7 segmentos com "segmentos fantasma", temas **Âmbar, Verde, Azul (negativo), Noturno, Branco**.
- **Roda do mouse sobre um dígito** altera aquele dígito; clique na metade de cima/baixo = +1/−1.
- **Entrada direta**: digite `145.57` + Enter (MHz) — ou `7100` + Enter (kHz).
- S-meter segmentado (S1…S9+60) com retenção de pico, leitura em dBm, indicadores
  AGC/NB/NR/NOTCH/EQ/SQL/TSQ/SCAN/REC/BUSY, canal de memória, banda, CTCSS detectado e relógio local/UTC.

### Waterfall / espectro
- Clique para sintonizar (com arredondamento ao passo), **arraste o passband** para sintonizar,
  **arraste as bordas** para mudar a largura (passband assimétrico, como no KiwiSDR).
- Zoom com a roda do mouse, botões de zoom rápido (Total/500k/200k/50k/10k), duplo clique = zoom total,
  **Ctrl+roda** = sintonia por passos.
- FFT de 1024 a 32768 pontos, velocidade (5–50 linhas/s), média do espectro, retenção de pico.
- Piso/teto ajustáveis e **Auto** (como o "auto-scale" do KiwiSDR).
- Paletas: Kiwi, SDR#, Fósforo, Âmbar, Cinza, Inferno.
- Histórico do waterfall **desloca junto** quando a frequência central muda.
- Marcadores das memórias e faixas do plano de bandas sobre o espectro.

### Demodulação e áudio
- Modos **NFM, WFM, AM, USB, LSB, CW, DSB, RAW** com larguras pré-definidas e ajuste fino.
- De-ênfase WFM 75 µs (Américas) ou 50 µs; de-ênfase opcional em NFM; tom de CW ajustável.
- **Squelch** por nível com histerese, botão **Auto** (6 dB acima do ruído) e **tom squelch (CTCSS)**.
- **AGC** rápido/médio/lento com *hang*, ou ganho manual.
- **Noise blanker** (IQ), **redução de ruído** espectral (NR), **notch** manual,
  filtro de sub-tom (<300 Hz) e passa-baixas de áudio.
- **Equalizador gráfico de 8 bandas** (100 Hz–12 kHz) com presets (Voz, Voz clara, Telefonia, Música…).
- Volume, mudo, limitador suave, escolha da placa de som.
- **Gravação** de áudio (WAV 48 kHz) e de **IQ** (WAV estéreo, compatível com SDR#/SDR++).

### Memórias prontas e favoritos
- **Pacotes de memórias prontas** (botão *Memórias prontas…*): radioamador (chamada e fonia),
  FT8/FT4/WSPR, satélites/ISS, aviação, marítimo VHF (simplex, DSC, AIS), PX 11 m (40 canais),
  FRS/PMR446 e sinais horários (WWV/CHU).
- **Barra de favoritos ★** acima do waterfall: teclas de memória de um clique, como num rádio.

### Scanner por espectro
- Varre faixas inteiras **pelo FFT**, segmento a segmento — salta direto para onde há sinal
  (centenas de canais por segundo com um RTL-SDR).
- Faixas prontas (aviação, marítimo, 2 m, 70 cm, VHF/UHF serviços, FRS, PMR446, PX, radiossondas,
  FM, ondas curtas) ou faixa personalizada; resolução e sensibilidade (dB acima do ruído) ajustáveis.
- **Só descobrir** (monta a lista de frequências ativas com acessos, horário, SNR e tempo ativo)
  ou **Parar e escutar** (retoma após o silêncio), **canal prioritário**, **bloqueio** de frequências.
- Salve as descobertas como memórias com um clique; exporte a lista em CSV.
- **Gravação automática por atividade**: cada transmissão vira um WAV, para ouvir depois.

![Gravação automática por atividade](docs/screenshot-atividade.png)

### Memórias e varredura
- Memórias com **categorias** (Repetidoras, Simplex, APRS/Digital, Satélites, Aviação, Marítimo, Broadcast…),
  banda detectada automaticamente, modo, largura, CTCSS, deslocamento de repetidora, notas, favoritos.
- **Importa/exporta CSV do CHIRP** (leve as memórias do seu HT para o SDR e vice-versa).
- **Varredura de memórias** por categoria, com tempo de permanência e retomada automática.
- Plano de bandas (IARU R2 / Brasil): HF, PX (11 m), 6 m, FM broadcast, aviação, 2 m, marítimo, 70 cm…
- VFO A/B, A⇄B, A=B.

### Novidades da 0.7
- **Instrumentos analógicos**: S-meter de ponteiro e VU de áudio com estilos Valvulado, Militar e Estúdio, selecionáveis na aba Display.
- **Atividade RF em 24 horas**: nova subaba no Scanner, com mapa de calor das detecções por frequência/hora, persistência e CSV. A amostragem não representa percentual de ocupação do espectro.
- **Mapa APRS**: botão em Decodificadores para abrir no navegador as estações recebidas e seus rastros, sem transmitir dados ao APRS-IS (tiles OSM exigem Internet).
- **Sinal fraco · IA + DSP**: perfil NB/NR/AGC com RNNoise neural opcional na fonia; controle de mistura no painel de áudio.
- **Legendas ao vivo**: transcrição local da fonia por blocos, com frequência, modo, idioma e indicativos, histórico e CSV. Requer `faster-whisper` e um modelo disponível; download e empacotamento do modelo ainda são opcionais.

### Novidades da 0.6
- Fonte RTL-SDR e interface Avançada como opções iniciais (preferências anteriores preservadas).
- Teclas de banda em duas linhas abaixo do display com acesso rápido e memória de até três frequências/modos.
- Bandas não suportadas esmaecidas e explicadas conforme o receptor configurado.
- Botão **Centralizar** / Ctrl+E e **Seguir VFO** preservando a escala de zoom.
- Campos de configuração compactos.

### Novidades da 0.5
- **Abas superiores** (Receptor, Memórias / Varredura, Scanner, Decodificadores, Receptores extras, Configurações)
  e cabeçalho com versão/atualização, Ligar/Desligar e relógio UTC.
- **Reconecta o receptor ao abrir** se o programa foi fechado com ele ligado.
- **Modo apresentação** (F11): tela cheia só com display e waterfall.
- Interface web pela rede local **direto pelo IP, sem chave** (opcional).

### Novidades da 0.4
- **Modo AUTO**, **auto-sintonizar ao selecionar** (tecla A-SINT), **◀ ▶ transmissão vizinha** e **modos clicáveis
  no display**.
- **Níveis de interface** Essencial / Intermediário / Avançado (menu Exibir ou barra do waterfall).
- **Gravação VOX** (pré-gravação de 0,5 s; arquivo único ou por transmissão; também IQ).
- **Aba Configurações** e **interface web** local/LAN: display, waterfall, APRS e áudio no navegador.
- **RTL-SDR robusto**: reconexão automática, aviso de faixa sem suporte, driver RTL-SDR Blog (V4) e
  **Preparar RTL-SDR** (driver WinUSB, como o Zadig).

### Assistente de sintonia, voltar no tempo e receptores extras
- **Auto-sintonia SSB**: corrige o VFO pela estrutura harmônica da voz (sem mexer no áudio); modo contínuo opcional.
- **Detectar modo**: WFM, NFM, AM, CW ou USB/LSB, ajustando modo, filtro e sintonia.
- **Ajustar filtro**: passband ajustado à largura real do sinal.
- **Voltar no tempo**: reouça os últimos 10–60 s de qualquer frequência da faixa.
- **Receptores extras**: até 4 canais da mesma faixa ao mesmo tempo.
- **Transcrição local opcional** das transmissões gravadas (`pip install faster-whisper`).

### Decodificadores
- **APRS / AX.25 1200 bd (AFSK Bell 202)** com vários fatiadores (compensa pré-ênfase, estilo Dire Wolf):
  posição normal e compactada, **Mic-E**, objetos, status, mensagens, **telemetria** (`T#`) e **estações meteorológicas**.
  Distância e azimute a partir do seu locator Maidenhead; tabela de estações; exporta log CSV.
- **DTMF** (Goertzel) e **CTCSS** (51 tons padrão).

### Fontes de sinal
| Fonte | Observações |
|---|---|
| RTL-SDR (USB) | ganho/AGC do sintonizador, correção ppm, **Bias-T**, **amostragem direta** (HF no RTL-SDR Blog V3/V4) |
| rtl_tcp | RTL-SDR remoto em rede (`rtl_tcp -a 0.0.0.0`) |
| SoapySDR | Airspy, HackRF, SDRplay, LimeSDR… (requer SoapySDR instalado) |
| Arquivo IQ | WAV estéreo I/Q; frequência lida do nome do arquivo (`…_145570000Hz_…`) |
| Simulador | banda de 2 m sintética com APRS, voz+CTCSS+DTMF, CW, AM, USB e uma FM em 98,1 MHz |

Taxas de amostragem: 0,24 / 0,96 / 1,2 / 1,44 / 1,92 / 2,4 / 2,88 MS/s (múltiplos de 240 kHz,
para decimação exata até 48 kHz).

## Instalação (Windows)

### Executável
Baixe o **instalador** ou a **versão portátil** em **https://www.pt2vhf.com/sdr** (downloads e
atualizações oficiais somente pelo site). O programa avisa quando há versão nova e se atualiza sozinho,
conferindo tamanho e SHA-256 do pacote.

### A partir do código
1. Instale o Python 3.10+ (64 bits).
2. No diretório do projeto:
   ```bat
   pip install -r requirements.txt
   python run_pt2vhf.py
   ```
3. Para gerar instalador e portátil localmente: `build_windows.bat` (requer Inno Setup 6).

### Driver do RTL-SDR
No Windows o dongle precisa do driver **WinUSB**: use o **Zadig** (Options → List All Devices →
"Bulk-In, Interface (Interface 0)" → WinUSB → Replace Driver). A biblioteca `librtlsdr` já vem com o
pacote `pyrtlsdr[lib]`.

## Atalhos
| Tecla | Ação |
|---|---|
| Alt+N / W / A / U / L / C | NFM / WFM / AM / USB / LSB / CW |
| Ctrl+← / → | passo de sintonia (no LCD com foco: ← / →) |
| Ctrl+↑ / ↓ | passo × 10 |
| Ctrl+M | salvar frequência atual na memória |
| Ctrl+B | trocar VFO A/B |
| Ctrl+S | squelch automático |
| Ctrl+L | níveis automáticos do waterfall |
| Ctrl+Shift+M | mudo |
| F11 | modo apresentação (tela cheia) |
| Ctrl+1 … 6 | abas |
| Esc | sair do modo apresentação / parar varredura |

## Arquitetura

```
pt2vhf/
  sources/      fontes IQ (RTL-SDR, rtl_tcp, SoapySDR, WAV, simulador) — thread de leitura + fila
  dsp/          filtros com estado, cadeia do receptor (NCO → decimação → filtro de canal → demod → áudio),
                AGC, squelch, NB, NR, notch, equalizador
  decoders/     AX.25/HDLC, modem AFSK1200, parser APRS, DTMF, CTCSS
  engine.py     thread DSP: espectro/waterfall, receptor, decodificadores, gravação
  audio.py      saída de áudio (PortAudio) com compensação de clock, gravadores WAV
  memory.py     memórias, categorias, plano de bandas, CSV do CHIRP
  presets.py    pacotes de memórias prontas
  scanner.py    scanner por espectro (detecção, segmentos, prioridade, bloqueios)
  ui/           display LCD, espectro/waterfall (pyqtgraph), painéis (docks), janela principal
```

Configurações e memórias ficam em `%APPDATA%\PT2VHF-SDR-Tool\` (Linux: `~/.config/PT2VHF-SDR-Tool/`).

## Testes
```bash
pip install -r requirements-dev.txt
python -m pytest -q
```
Os testes cobrem filtros, demoduladores, AFSK/AX.25/APRS (incluindo Mic-E e compactado),
DTMF, CTCSS, memórias/CSV, protocolo rtl_tcp, arquivo IQ, a cadeia completa com o simulador
e um teste da interface (offscreen).

## Changelog
Veja [CHANGELOG.md](CHANGELOG.md).

## Próximos passos (roteiro)
- Cliente para receptores **KiwiSDR** remotos e servidor web próprio.
- Mapa APRS, envio para APRS-IS (iGate RX-only).
- POCSAG/FLEX, ADS-B, AIS, ACARS, satélites meteorológicos (APT), radiossondas.
- Áudio estéreo (WFM) e RDS.
- Previsão de passagens de satélite e correção Doppler.
- Controle CAT (Hamlib) para sincronizar com o rádio.
