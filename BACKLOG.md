# Backlog — PT2VHF SDR Tool

Itens registrados pelo mantenedor. Não implementar até o pedido de versão nova.

## Pendentes

### Indicador de versão / atualização no topo da janela, como nos demais programas (registrado em 07/11/2026)
- Hoje o botão de versão ("v0.4.x" / "Nova versão X · atualizar" / progresso) fica no canto inferior direito, na barra
  de status, e passa despercebido.
- Mover para o **topo da janela**, como no PT2VHF Sat Tool (botão de versão na barra superior), com os mesmos estados:
  versão atual, "Nova versão X · atualizar", "Atualizando… N%", "instala ao ficar livre" e falha/tentar novamente;
  clique verifica ou inicia a atualização.
- Combinar com o item das abas superiores (Configurações) para ficar visível em todos os níveis de interface.

### Abas superiores com "Configurações"; receptor e modo/filtro dentro dela; tirar os modos duplicados (registrado em 07/11/2026)
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
