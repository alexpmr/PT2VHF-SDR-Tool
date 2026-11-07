# Backlog — PT2VHF SDR Tool

Itens registrados pelo mantenedor. Não implementar até o pedido de versão nova.

## Pendentes

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
