# Backlog — PT2VHF SDR Tool

Itens registrados pelo mantenedor. Não implementar até o pedido de versão nova.

## Pendentes

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
