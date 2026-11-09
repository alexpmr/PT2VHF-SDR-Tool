# Backlog — PT2VHF SDR Tool

Itens registrados pelo mantenedor. Implementar somente com solicitação de versão; distinguir código, testes, homologação e publicação.

## P0 — restaurar OTA automático com instalação e notas da versão (09/11/2026)
- **Falha confirmada:** ao detectar uma versão nova, o programa anuncia a atualização, mas abre a página no navegador em vez de baixar e instalar. O site publica `download.php?product=sdr&file=...` (com entrega/redirect da release), enquanto `updater.is_official()` aceita apenas caminho `/downloads/sdr-tool/<arquivo>` sem query/redirecionamento. `UpdateController._on_checked()` utiliza o navegador quando `UpdateInfo.file` é `None`.
- **Comportamento solicitado:** nos builds Windows instalador e portátil, a verificação automática detecta nova versão, inicia **download no próprio aplicativo**, exibe progresso/estado, valida tamanho e SHA-256, aguarda janela segura para aplicação, encerra o processo, aplica Setup silencioso ou substitui EXE portátil com backup e reabre a versão nova. Preservar configuração, memórias, dados e poder recuperar a edição portátil anterior se falhar.
- **Novidades após atualizar:** **na primeira abertura da nova versão instalada**, exibir uma única vez um diálogo com versão, data e notas de lançamento oficiais (texto não executável), registrando a última versão cujas novidades foram exibidas. Não reapresentar em cada abertura nem confundir o anúncio institucional de abertura com as novidades da release.
- **Contrato seguro de download:** corrigir compatibilidade site/cliente e validar URL/domínio/arquivo/versão antes do download; se houver redirecionamento, restringir estritamente a origem e o caminho esperado da release GitHub, com arquivo/tamanho/hash correspondentes ao manifesto do site. Rejeitar destinos arbitrários, alteração de esquema, hash ausente, download incompleto, substituição de executável sem validação ou downgrade involuntário. Não enfraquecer assinatura/controle de integridade para corrigir o OTA.
- **Falhas/aceite:** erro de rede, arquivo corrupto, HTTP 302, proxy e ausência de permissão devem gerar diagnóstico e opção de tentar novamente, sem abrir navegador como fluxo padrão. Diferenciar instalação normal, portable e código-fonte (sem auto-instalação para fonte). Testar 0.12.0 → 0.13.0 em Windows real e fluxo completo de próxima versão, inclusive retomada/rollback, histórico de novidades, reinício automático, progresso e `update.php` público. **Status: backlog, ainda sem implementação ou homologação.**

## Estado da v0.13.0 — 09/11/2026
- **Publicado:** GitHub Release v0.13.0 com Setup/Portable Windows x64, hashes SHA-256 e build CI Windows/Linux aprovado (SHA `067920719c69eda68b5c5c850d09ca731f257fae`).
- **Site:** catálogo público `updates.json` e endpoint `update.php?product=sdr` anunciam v0.13.0. Downloads passam pelo site e seguem até a release do GitHub. O workflow de segmentação dos arquivos no repositório do site falhou antes de executar os passos.
- **Pendente P1 — OTA:** `update.php` fornece URLs `download.php?product=sdr&file=...`, mas o `updater.py` somente aceita `/downloads/sdr-tool/...` e não segue redirecionamentos. **Atualização automática não homologada**; manter SHA-256/tamanho/origem oficial ao corrigir. Download manual disponível na página oficial.
- **Pendente de homologação:** testes com SDR real (RS41, bandas, S-meter), interface Windows em monitores diversos e qualidade de transcrição. Decodificadores RF adicionais seguem no backlog.


## P1 — tamanho ajustável do LCD e ocultação de bandas incompatíveis (09/11/2026)
- **Redimensionamento pelo usuário:** permitir aumentar ou reduzir o tamanho do display LCD diretamente na interface ou em `Configurações → Display`, com controle claro e previsível; salvar a **última dimensão/escala escolhida** nas preferências e restaurá-la após reiniciar o aplicativo.
- **Escala uniforme:** redimensionar proporcionalmente todos os elementos do LCD — frequência, fontes, segmentos, S-meter, indicadores, teclas de modo, matriz de bandas e áreas clicáveis — sem distorção, recorte, sobreposição ou perda de cliques. Preservar a proporção original ao maximizar/restaurar, trocar monitor, reduzir a janela ou usar modo apresentação; limitar temporariamente a escala ao espaço disponível sem substituir o tamanho preferido salvo.
- **Bandas incompatíveis não aparecem:** na matriz de seleção rápida dentro do LCD, **ocultar completamente** as bandas fora do alcance do SDR atualmente selecionado/conectado; não exibir botões esmaecidos ou clicáveis para essas bandas. Determinar a compatibilidade por capacidades efetivas do dispositivo/fonte (incluindo direct sampling, conversores e limitações do driver), sem tratar ausência de suporte como autorização para sintonizar.
- **Atualização dinâmica:** recalcular os botões visíveis ao conectar/desconectar, trocar fonte ou receptor, alterar direct sampling ou atualizar as capacidades reportadas pelo driver. Exibir apenas a interseção entre bandas configuradas pelo usuário e bandas realmente disponíveis; não apagar da configuração as preferências de bandas ocultadas. Sem capacidade conhecida, não inventar suporte; apresentar estado de receptor/capacidade ainda não identificada.
- **Layout/aceite:** reorganizar a grade de até 5 colunas conforme a quantidade de bandas disponíveis sem espaços vazios ou controles sobrepostos; verificar RTL-SDR V3/V4 (inclusive HF), simulador, rtl_tcp e SoapySDR quando houver hardware; conferir persistência após reinício, monitores de tamanhos diferentes, os 5 temas, modo apresentação e cliques após escala. Testes Qt automatizados e homologação visual em Windows.
- **Precedência:** este pedido substitui a regra anterior de `bandas indisponíveis esmaecidas`; o redimensionamento automático existente não atende sozinho à exigência de **ajuste manual persistente**.
- **Status:** escala persistente e ocultação de bandas implementadas na v0.13.0, com CI e build Windows aprovados e catálogo publicado no site; faltam homologação visual/SDR real e correção do OTA.

## Legendas ao vivo — atualização de interface (09/11/2026)
- **Implementado no código (sem nova release):** a aba `Legendas ao vivo` sai de Scanner e passa a `Ferramentas → Legendas ao vivo`, reservada a histórico e exportação CSV.
- **Ferramentas → Transcrição:** download e escolha de modelo Whisper, idioma, habilitação de legendas e opção de transcrever gravações do Scanner concentrados no mesmo lugar.
- **Popup de transcrição:** quando legendas são habilitadas, abrir a aba principal `Receptor` e sobrepor janela contrastante com **somente o texto reconhecido** (sem frequência, horário, indicativos ou modo). Mostrar mensagem de espera antes da primeira fala; remover imediatamente o popup ao desativar. Atualizar os trechos reconhecidos a cada resultado do worker sem bloquear RF/áudio.
- **Navegação complementada em código:** `Decodificação` reúne ADS-B, Sondas Meteorológicas, AIS e APRS/DTMF/CTCSS; aba principal Satélites removida sem apagar biblioteca orbital.
- **Falta homologar:** testes Linux/Qt, teste visual Windows pequeno/máximo, recepção com fala real, desempenho de CPU e publicação de novo instalador/site/OTA. Não declarar liberado sem CI e artefato verificados.

## Reorganização da navegação — solicitada em 09/11/2026
- **Criar aba principal `Decodificação`** e agrupar nela, como subabas, **ADS-B**, **Sondas Meteorológicas** e **AIS**, retirando essas três abas da navegação principal sem perder suas telas e funcionalidades.
- **Remover a aba principal `Satélites`** da interface, sem deixar guia ou página vazia. O pedido é de remoção da aba; não autoriza, por si só, apagar dados ou módulos de previsão e controle de satélites do código.
- **Critérios de aceite:** as três seções de decodificação continuam acessíveis em `Decodificação`, com estados e recursos preservados; `Satélites` desaparece da navegação principal; conferir layout estreito, modo apresentação e traduções dos títulos.
- **Precedência:** este pedido substitui a orientação anterior do backlog que determinava manter ADS-B, AIS e Sondas Meteorológicas como abas principais separadas.

### Ferramentas e sinais auxiliares — 09/11/2026
- **Criar a aba principal `Ferramentas`**, caso ainda não exista, e nela a subaba **`Transcrição`**. Centralizar nessa subaba as **configurações de transcrição de áudio** atualmente expostas em `Scanner → Legendas ao vivo` (escolha de modelo Whisper tiny/base/small, download e status do modelo, idioma/detecção automática e parâmetros de transcrição existentes). Evitar opções de configuração duplicadas em outras abas.
- **Preservar a experiência de legendas em tempo real** sob o LCD quando ativadas. Manter acessíveis as legendas reconhecidas, histórico e exportação CSV; a reorganização não deve desativar recursos já funcionais.
- **Mover `APRS / DTMF / CTCSS` de `Scanner` para `Decodificação`**, como quarta subaba, preservando seus controles e decodificação. O protocolo correto é **DTMF** (não "DTML").
- **Navegação desejada em `Decodificação`:** ADS-B | Sondas Meteorológicas | AIS | APRS / DTMF / CTCSS.
- **Aceite:** os controles de transcrição aparecem em `Ferramentas → Transcrição`; `Scanner` não apresenta mais abas duplicadas de configuração ou `APRS / DTMF / CTCSS`; quatro subabas operacionais em `Decodificação`; manter recursos, estado, ajustes persistidos, traduções e responsividade.

## Revisão v0.12.0 — IA neural e transcrição
- **IA neural na fonia:** RNNoise (RNN) em worker 48 kHz, ativa em NFM/AM/USB/LSB/DSB, com controle de intensidade e fila limitada. Não interfere nos dados IQ, APRS nem no S-meter.
- **Transcrição local:** faster-whisper/CTranslate2 no empacotamento e modelos tiny/base/small baixados por solicitação explícita. Recepção ao vivo gera legendas com frequência, horário, idioma e indicativos; WAV do Scanner usa o mesmo modelo.
- **Testes:** mock RNNoise, buffering, fila sob sobrecarga, bypass digital, modelo local sem rede, transcrição em worker e autoteste de dependências nos executáveis.
- **Ainda pendente:** homologação SDR/RF real, análise de latência e CPU no Windows, tradução de voz, IA de IQ/filtragem adaptativa, CW neural, métricas SNR comparativas e demais decodificadores RF. Não confundir inclusão da IA de áudio com conclusão total de IA descrita no backlog.
- **Distribuição:** versão pronta somente após build Windows completo, publicação e SHA-256; site e OTA verificados separadamente.

## Revisão da v0.11.0 — status por evidência
- **LCD responsivo e matriz de bandas (implementados em código):** desenho em escala uniforme, botões em 5 colunas na área solicitada, sem banda abaixo dos modos. Faltam screenshots/homologação pelo operador em Windows e monitor pequeno.
- **S-meter preso em sete barras (correção em código):** o valor inicial de -127 dBm acendia 7 segmentos mesmo antes de amostra válida. Agora o medidor inicia sem barras, exige leitura IQ recente, recalcula segmentos e informa dBFS/dBm no tooltip. Falta validar com antena/receptor físico e calibração.
- **RS41 (hipótese técnica corrigida, P0 ainda aberto):** corrigida janela incompatível do fsk_demod (FI +12 kHz, máscara ±5 kHz); agora centro em 0 Hz e busca -5/+5 kHz. Teste de recepção de RS41 real continua obrigatório. A instalação fsk_demod/rs41mod continua separada.
- **Não concluídos:** além da homologação RS41, continuam IA neural, SSTV, DMR/D-STAR/C4FM, ADS-B/AIS nativos, tradução integral da interface e voz, ACARS/POCSAG, NOAA/Meteor, KiwiSDR e demais itens descritos abaixo. Não declarar "100% do backlog atendido".
- **Site:** não considerar publicação/OTA concluídos sem manifesto e arquivos públicos verificados.

## Falha P1 — S-meter / intensidade de sinal fixa em sete barras vermelhas (08/11/2026)
- **Relato do operador:** o indicador gráfico de intensidade de sinal permanece exibindo **sete barras na cor vermelha**, sem acompanhar variações reais de intensidade ou a mudança de frequência, mesmo recebendo transmissões distintas. Tratar como **falha funcional aberta**, ainda sem causa comprovada.
- **Fluxo existente a inspecionar:** `Receiver.process()` mede a potência do IQ filtrado em `rx.signal_db` (`pt2vhf/dsp/receiver.py`); `SDREngine.process_block()` publica `status["signal_db"]`; `MainWindow._tick()` converte `dbfs_to_s_units(..., s_meter_cal)` e chama `LCDDisplay.set_signal()`; `LCDDisplay._draw_smeter()` desenha a barra colorida e a indicação de pico. Investigar cada estágio para determinar se o valor congela no DSP, status, conversão/calibração, atualização do widget ou pintura; não presumir falha visual sem comparar medições.
- **Diagnóstico de escala:** verificar a inconsistência entre o comentário de faixa do S-meter e o limite efetivo da escala (`lo=-147 dBm`, `S9=-93 dBm`, `hi=-33 dBm`), o offset `s_meter_cal`, arredondamento do número de segmentos, retenção de pico (`_peak`) e regiões de cor vermelha. O medidor deve ser proporcional ao valor medido, não a uma quantidade fixa de barras ou ao squelch/AGC do áudio.
- **Testes reproduzíveis:** comparar sem sinal/antena, ruído de fundo, portadora fraca, média e forte; trocar de frequência, modo, ganho e fonte (RTL-SDR real e simulador). Registrar amostras de `signal_db` (dBFS), dBm calibrado, unidade S e `lit/peak` em segmentos por segundo. Confirmar atualização contínua do valor digital e da barra, inclusive em tema âmbar e nos demais temas.
- **Aceite:** o número de segmentos acesos sobe e desce acompanhando a potência do canal selecionado; o trecho vermelho só aparece ao ultrapassar o nível correspondente da escala; o marcador de pico decai no tempo correto; os valores numéricos e gráfico representam a **mesma leitura**. Ausência de sinal deve mostrar leitura baixa e sinal forte deve aumentar; testes automatizados com níveis IQ conhecidos e teste de bancada com SDR real.
- **Status:** **pendente de correção e homologação**. Não marcar como resolvido apenas com alterações de aparência ou com testes do simulador.

## Ajuste P1 — grade de bandas no espaço direito do LCD e escala responsiva (08/11/2026)
- **Referência visual:** imagem do mantenedor de 08/11/2026, com área delimitada em azul **à direita dos dígitos da frequência, acima do S-meter**, na porção livre do painel âmbar.
- **Alteração de posição:** retirar a grade de bandas atualmente desenhada como duas fileiras **abaixo das teclas de modos**. Colocar as teclas diretamente na região marcada, **dentro do mesmo LCD**, sem barra/painel independente e sem esconder as teclas AUTO/NFM/WFM/AM/USB/LSB/CW/DSB/RAW/A-SINT.
- **Grade de até 5 colunas**, com tantas linhas quanto necessárias para as bandas **habilitadas nas configurações e suportadas pelo SDR atual**; ordenar conforme o plano de bandas. Cada tecla deve ter o mesmo estilo visual das **teclas de modo do LCD** (contorno, preenchimento ativo, tipografia, cantos e contraste), sem parecer um widget Qt separado ou uma faixa solta. Bandas indisponíveis ficam **ocultas**, não esmaecidas; preservar destaque da banda ativa e tooltips das disponíveis.
- **Layout do painel direito:** reorganizar a área do LCD para que a matriz não se sobreponha aos dígitos, unidade MHz, S-meter, indicadores BUSY/MEM/banda/CTCSS, hora ou dBm. Onde necessário, compactar/mover os indicadores secundários sem perder informação.
- **Responsividade obrigatória:** quando a janela, o monitor, uma tela remota ou o modo apresentação dispuser de menos largura/altura, **reduzir o LCD inteiro proporcionalmente** (frequência, segmentos, S-meter, indicadores, fontes, teclas de modo, matriz de bandas, hitboxes), mantendo a proporção original e **sem cortar/podar** elementos, números ou controles. Ajustar o widget em resizeEvent/sizeHint/heightForWidth e usar escala única de desenho/layout; preservar o mapeamento correto de cliques/roda do mouse às coordenadas escaladas. Se necessário, usar margens internas/letterboxing em vez de crop/overflow.
- **Aceite:** em janela larga, janela estreita e modo apresentação, todos os itens do LCD continuam visíveis; matriz completa com 5 colunas na região marcada; botões clicáveis e feedback de seleção; nenhum botão de banda abaixo da fileira de modos; evidências visuais/screenshot nos 5 temas; regressões automatizadas Qt para resize e clique em coordenadas escaladas.
- **Status:** correção implementada em código da v0.11.0; validação visual em monitores pequenos e no Windows permanece pendente.

## Revisão da v0.10.0 — implementação e critérios de aceite
- **Interface (implementado em código):** abas principais ADS-B, AIS e Sondas Meteorológicas separadas; APRS/DTMF/CTCSS preservados dentro do Scanner; retirada a aba iGate RX. Confirmar em Windows Setup/Portable e resolução estreita.
- **LCD (implementado em código):** teclas de bandas estão no contorno do LCD, com layout e cores dependentes do tema, mantendo teclas de modo e estados. Confirmar redimensionamento, modo apresentação e visualização em monitor estreito.
- **Sondas (diagnóstico implementado; P0 ainda aberto):** exibição de perdas de IQ, quadros JSON, falhas dos subprocessos, linhas sem GPS e captura IQ por 20s. **Não afirmar que a RS41 já decodifica em RF real:** instalar e validar fsk_demod/rs41mod e realizar teste com gravação RS41.
- **Rastros (implementado em código):** histórico/OSM/GPX/KML para sondas, ADS-B e AIS; feeds ADS-B/AIS continuam externos.
- **Infraestrutura de publicação:** versionamento GitHub, artefatos Windows, atualização do manifesto/OTA no site com contagem cumulativa; site só é concluído quando live.

## Interface LCD — integrar teclas de seleção de bandas ao próprio display (registrado em 08/11/2026)
- **Solicitação:** mover os botões de seleção rápida de bandas, atualmente exibidos em uma barra independente **abaixo** do display LCD, **para dentro do contorno/painel visual do LCD** (referência: imagem enviada pelo mantenedor em 08/11/2026).
- **Layout:** inserir uma fileira ou duas fileiras compactas de teclas de banda na região inferior do LCD, compatíveis com a fileira existente de modos (AUTO/NFM/WFM/AM/USB/LSB/CW/DSB/RAW/A-SINT), **sem substituir as teclas de modos**, sem cobrir frequência, indicadores, medidor S, horário ou demais leituras. Priorizar largura fluida, displays pequenos e modo apresentação; se necessário, oferecer agrupamento/alternância de bandas sem rolagem horizontal obrigatória.
- **Identidade visual:** as teclas passam a pertencer ao painel LCD, com fundo, bordas, tipografia, contraste e estado ativo coerentes com os temas visuais existentes (inclusive tema âmbar apresentado); evitar uma segunda barra escura solta na página.
- **Comportamento preservado:** bandas configuradas como visíveis **e suportadas pelo SDR**, seleção e destaque da banda ativa, sintonia e restauração de frequência/modo por banda, tooltips e atualização ao trocar dispositivo devem continuar funcionando. Bandas incompatíveis **não aparecem na matriz**, sem apagar as preferências salvas.
- **Aceite:** nenhuma barra independente de bandas abaixo do LCD; todos os botões de bandas visíveis na área interna do LCD, sem sobreposição de controles ou perda de informações, com screenshot em monitor normal e estreito e testes de tema/navegação.
- **Status:** implementado no código da v0.10.0; **homologação visual em Windows ainda pendente**.

## Prioridade P0 — RS41 não decodifica sinal real (registrado em 08/11/2026)
- **Relato confirmado pelo operador:** a transmissão de uma radiossonda **Vaisala RS41** aparece no waterfall do SDR Tool v0.9.0, na frequência correta, porém **nenhum quadro ou telemetria é decodificado**. Isso não é um caso de protocolo de sonda diferente. Status: **falha funcional aberta / sem homologação**. O pipeline IQ adicionado na v0.9.0 não atende ao critério de aceite.
- **Reproduzir:** ligar o SDR, sintonizar RS41 ativa de 400–406 MHz, abrir o monitor de IQ e iniciar a decodificação; waterfall exibe emissões, tabela permanece vazia. Registrar frequência, taxa de amostragem, ganho, PPM, SNR, estado do decoder e existência/caminho das ferramentas fsk_demod/rs41mod.
- **Instrumentar ponta a ponta:** adicionar indicadores de IQ entrando, amostras descartadas, centro IQ e deslocamento real do canal, taxa/ganho, estado dos subprocessos e logs de stderr, símbolo/FSK sincronizado, quadros detectados, CRC/FEC válido, JSON emitido, JSON descartado e causa. Atualmente stderr é descartado e frames sem coordenadas podem ser silenciosamente filtrados.
- **Investigar:** compatibilidade das opções CLI e executáveis instalados de fsk_demod/rs41mod, sentido do deslocamento de FI, filtragem e decimação (continuidade entre blocos), frequência real/PPM, saturação, demodulação FSK e saída de telemetria. Comparar com cadeia de referência radiosonde_auto_rx usando **a mesma gravação IQ**, para diferenciar problema de entrada SDR, DSP, FSK, protocolo e interpretação JSON. Não presumir que testes sintéticos comprovam decodificação RF.
- **Corrigir experiência de usuário:** avisar sobre ferramentas ausentes, processo terminado, falta de sincronismo/CRC e status "sinal detectado, sem quadros válidos". Não mostrar falso status "decodificando" só porque o processo iniciou.
- **Aceite obrigatório:** ao menos uma gravação IQ RS41 real de referência com serial, nº do frame, horário, latitude, longitude e altitude válidos; teste com emissão RS41 física usando o SDR Tool; regressão Windows Setup e Portable; demonstrar que a telemetria chega à tabela e ao mapa, sem processos travados, com métricas de erro visíveis. Até cumprir, manter **RS41 = não funcional / P0**.

## Prioridade P1 — Reorganização das abas do SDR Tool (registrada em 08/11/2026)
- **Remover a aba principal "Decodificadores"** como contêiner genérico; redistribuir os recursos existentes, preservando APRS/DTMF/CTCSS que ainda forem utilizados em uma área apropriada de recepção/sinais.
- **Remover "APRS iGate RX" da navegação e das funcionalidades expostas**, sem ativação automática nem tráfego APRS-IS; revisar dependências e não deixar componentes órfãos.
- **Substituir a aba intitulada "RS41 · IQ ao vivo" por uma aba principal "Sondas Meteorológicas"**, com suporte à RS41 e arquitetura para outros modelos sem mudar novamente o nome.
- **Centralizar em "Sondas Meteorológicas"** tanto a recepção/decodificação do IQ quanto a importação de telemetria JSON, status, frequências, identificação do modelo, lista de sondas, mapa, gráficos e registros.
- **Separar "ADS-B" e "AIS" em abas independentes**, removendo a aba híbrida "ADS-B / AIS / Sondas". A aba ADS-B só contém aeronaves e a AIS só embarcações, sem subtela "Sonda".
- **Aceite UI:** não haver abas duplicadas de sonda, nem abas "Decodificadores", "RS41 · IQ ao vivo" ou "APRS iGate RX"; todos os recursos preservados devem ser acessíveis em seu novo local; navegação, níveis de interface e traduções devem refletir os novos títulos; testes Qt e screenshots de homologação.

## Revisão v0.9.0
- **Incidente radiossonda:** na v0.8.0 só havia importação JSON, por isso ver o waterfall não produzia decodificação. Na v0.9.0 há pipeline do IQ do próprio SDR para fsk_demod + rs41mod, mas ainda depende de executáveis externos e só suporta RS41. A correção não está homologada com sinal RF real nem cobre modelos diferentes.
- **Satélites:** SGP4 e Doppler RX com TLE local, sem controle rotor ou decodificação de imagens.
- **APRS:** iGate RX-only opcional, exige passcode verificado; validação em rede real pendente.
- **Idiomas:** seletor com 7 bandeiras e catálogo parcial; tradução completa continua no backlog.
- **Ainda pendente:** decodificação nativa multissonda (DFM, M10/M20, RS92 etc.), IA neural, SSTV, DMR/D-STAR/C4FM, ACARS, RDS, tradução local integral, ADS-B/AIS IQ, NOAA APT/Meteor LRPT, POCSAG/FLEX, KiwiSDR remoto, previsão de queda e ajustes restantes.

## Pendentes

> Revisão do backlog em 0.8.0 (08/11/2026): foram adicionadas interfaces para
> feeds **externos** ADS-B, AIS e radiossondas, CAT Hamlib e mapas de posição;
> os demoduladores RF internos, o Doppler, RS41 IQ, tradução, IA neural e fonia
> digital continuam pendentes. O fato de existir integração de arquivo **não**
> conclui o pedido de decodificação direto no SDR. A v0.7.0 já foi aprovada.
>
> Revisão da versão 0.7.0 (08/11/2026): a 0.6.0 já incorporou teclas de banda,
> memória por banda, centralização, padrões do receptor, prévias LCD e seleção das bandas exibidas.
> A 0.7.0 adicionou instrumentos S/VU analógicos, mapa de detecções RF 24 h,
> perfil de escuta "Sinal fraco" por DSP convencional, mapa APRS local sem iGate e legendas locais com
> faster-whisper **opcional**. Permanecem pendentes: IA neural, tradução,
> decodificadores avançados, radiossondas e internacionalização integral.
> Os detalhamentos abaixo permanecem como backlog até validação completa.


### Teclas de banda no display (um botão por banda) (registrado em 08/11/2026)
- **Atualização de requisito (09/11/2026; substitui esmaecimento de 08/11):** **ocultar** as teclas de bandas que o SDR em uso não suporta, conforme a faixa real do dispositivo/sintonizador e modo (ex.: R820T sem amostragem direta não recebe HF; V4 pode receber HF pelo conversor; demais fontes segundo capacidade real informada pelo driver). Atualizar ao trocar de fonte/dispositivo ou alterar amostragem direta. Nenhuma banda incompatível deve aparecer como botão clicável; sem receptor identificado, não pressupor capacidade de recepção.
- Hoje a banda só se escolhe na lista "Bandas" em Configurações → Modo / Filtro.
- Colocar no **display** uma fileira de teclas de banda, como num transceptor: **160, 80, 60, 40, 30, 20, 17, 15,
  12, 10, 6, 2 m, 70 cm** (e outras faixas úteis para escuta, ex.: PX/11 m, FM broadcast, aviação, marítimo),
  um clique por banda.
- Ao clicar, ir para a banda com o modo adequado (LSB abaixo de 10 MHz, USB acima, FM em VHF/UHF, conforme o plano
  de bandas) e **lembrar a última frequência/modo usados em cada banda** (band stacking), voltando nela no
  próximo clique; segundo clique na mesma banda pode alternar entre posições salvas (CW / SSB / digital).
- Destacar a banda atual; **ocultar** do LCD bandas fora do alcance do dispositivo (ex.: HF no RTL-SDR sem amostragem direta ou conversor HF). Manter a preferência salva para quando houver SDR compatível.
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
- 0.8.0 (código) — leituras de tráfego ADS-B via JSON readsb/dump1090, AIS NMEA com MMSI,
  radiossondas por JSON, tabela e mapa unificados, CSV, CAT Hamlib rigctld sem PTT,
  bancos de memórias por região/cidade com importação CHIRP CSV.
  **Dependem de decodificadores externos** e não substituem as implementações de RF nativas.
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
