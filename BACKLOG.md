# Backlog — PT2VHF SDR Tool

Itens registrados pelo mantenedor. Não implementar até o pedido de versão nova.

## Pendentes

### Modo apresentação (tela cheia sem as barras do Windows) (registrado em 07/11/2026)
- Modo que ocupa a tela inteira, escondendo a barra de título da janela e a barra de tarefas do Windows
  (tela cheia de verdade), para exibição em monitor/TV ou apresentações.
- Acesso por menu Exibir → "Modo apresentação", atalho (ex.: F11) e um botão discreto; Esc ou F11 para sair.
- Opção de esconder também menu, barra de status e painéis, deixando só display + waterfall (com os painéis
  reabríveis); lembrar a preferência; funcionar em vários monitores (abre no monitor onde está a janela).

### Lembrar o estado do receptor ao sair e reconectar ao abrir (registrado em 07/11/2026)
- Hoje o programa sempre abre desligado e com a fonte "Simulador" selecionada por padrão; o usuário precisa escolher
  o RTL-SDR e clicar em Ligar a cada abertura.
- Ao fechar, memorizar: fonte (RTL-SDR, rtl_tcp, SoapySDR, arquivo, simulador), dispositivo/endereço, taxa de amostragem,
  ganho/ppm/bias-T/amostragem direta e se o receptor estava **ligado**.
- Ao abrir: se foi fechado **ligado com um dispositivo real**, reconectar automaticamente na mesma fonte, frequência e
  modo (sem cair no simulador); se o dispositivo não estiver presente ou não abrir, avisar sem travar e deixar a fonte
  escolhida pronta para tentar de novo. O simulador só é padrão na primeira execução (sem configuração salva).
- Opção em Configurações: "Reconectar o receptor ao abrir" (ligada por padrão).

### PRIORIDADE — 0.4.1 ainda não abre o RTL-SDR (dithering -1 + LIBUSB_ERROR_ACCESS) (registrado em 07/11/2026)
- **Relato do mantenedor (com imagem):** "driver RTL-SDR Blog: Error code -1 when setting PLL dithering mode;
  biblioteca padrão: <LIBUSB_ERROR_ACCESS (-3)>…". Driver no Windows: interface 0 WinUSB, interface 1 WinUSB (correto).
- **Causa (confirmada no código do pyrtlsdr 0.5):** `RtlSdr.open()` chama `rtlsdr_set_dithering` logo após
  `rtlsdr_open`; a DLL do driver Blog V1.4.0 não tem essa função e o substituto da 0.4.0/0.4.1 respondia -1 → o pyrtlsdr
  abortava **com o dongle já aberto**, e a biblioteca padrão recebia ACCESS (WinUSB é exclusivo). Explica também o erro
  da 0.4.0.
- **Correção já feita no código (falta gerar e publicar a versão):** funções ausentes respondem 0 (sem efeito); se a
  abertura falhar depois de abrir o dongle, o handle é fechado antes da próxima tentativa. Teste
  `test_open_failure_after_handle_releases_dongle_and_stub_returns_ok` reproduz o cenário da imagem.

### Indicador de versão / atualização no topo da janela, como nos demais programas (registrado em 07/11/2026)
- Hoje o botão de versão ("v0.4.x" / "Nova versão X · atualizar" / progresso) fica no canto inferior direito, na barra
  de status, e passa despercebido.
- Mover para o **topo da janela**, como no PT2VHF Sat Tool (botão de versão na barra superior), com os mesmos estados:
  versão atual, "Nova versão X · atualizar", "Atualizando… N%", "instala ao ficar livre" e falha/tentar novamente;
  clique verifica ou inicia a atualização.
- Combinar com o item das abas superiores (Configurações) para ficar visível em todos os níveis de interface.

### Abas superiores (como nos demais programas PT2VHF): Configurações, painéis inferiores e sem modos duplicados (registrado em 07/11/2026)
- **Acréscimo (07/11/2026):** mover também os painéis da parte inferior — Memórias / Varredura, Scanner,
  Decodificadores, Receptores extras e Configurações — para **abas na parte de cima**, no mesmo padrão de abas dos
  demais projetos PT2VHF (ex.: Sat Tool), em vez de docks embaixo; a área principal fica para display + waterfall.
  Conferir o layout de abas dos outros programas antes de implementar.
- Criar **abas na parte superior** da janela, entre elas **Configurações**.
- Mover para dentro de Configurações o que hoje ocupa a página principal: o bloco **Receptor** (fonte, dispositivo,
  amostragem, ligar, ganho/ppm/bias-T/amostragem direta) e o bloco **Modo / Filtro** (VFO, filtro/passo, bandas,
  assistente, tom CW, de-ênfase), liberando espaço para display e waterfall.
- **Tirar os botões de modo** do painel Modo/Filtro: os modos já estão no display (AUTO, NFM, WFM, AM, USB, LSB,
  CW, DSB, RAW). Manter os atalhos Alt+… e as teclas do display.
- Unificar com a aba Configurações atual (hoje dock inferior); o botão Ligar/Desligar deve continuar acessível
  na tela principal (ex.: no topo ou no display), já que o receptor sai da página principal.
- Respeitar os níveis Essencial/Intermediário/Avançado e o "Restaurar layout padrão".

### Interface web: abrir de outro computador direto pelo IP, sem chave (registrado em 07/11/2026)
- Hoje, com "Permitir outros dispositivos da rede local (LAN)", o endereço precisa da chave temporária
  (`http://IP:porta/?key=…`); sem ela o navegador recebe "Acesso negado".
- Pedido: permitir abrir digitando só `http://IP:porta/` em outro computador da rede.
- Proposta: opção em Configurações → Interface web "Exigir chave na rede local" (desmarcada = acesso direto pelo IP),
  com aviso de que qualquer dispositivo da rede poderá ver e ouvir a sessão (continua somente leitura);
  aceitar apenas endereços de rede privada (10/8, 172.16/12, 192.168/16, link-local) quando sem chave;
  mostrar o endereço `http://IP:porta/` pronto para copiar; manter a chave como opção para redes compartilhadas.

## Concluídos
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
