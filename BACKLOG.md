# Backlog — PT2VHF SDR Tool

Itens registrados pelo mantenedor. Não implementar até o pedido de versão nova.

## Pendentes

### PRIORIDADE — 0.4.0 não abre o RTL-SDR: LIBUSB_ERROR_ACCESS (registrado em 07/11/2026)
- **Relato do mantenedor (com imagem):** na 0.4.0, ao ligar o RTL-SDR aparece "Não foi possível abrir o RTL-SDR #0:
  <LIBUSB_ERROR_ACCESS (-3): Access denied (insufficient permissions)> Could not open SDR (device index = 0)".
  **Na 0.3.0 o mesmo dongle abria perfeitamente.**
- **O que mudou na abertura (código):** a 0.3.0 usava a librtlsdr do `pyrtlsdrlib`; a 0.4.0 usa a DLL do driver
  RTL-SDR Blog V1.4.0 incluída no pacote (libusb própria, embutida). Hipóteses, em ordem:
  1. a libusb da DLL Blog não trabalha com o driver instalado no dongle (ex.: libusbK/libusb-win32 do Zadig, ou
     WinUSB instalado de outra forma) e devolve ACCESS;
  2. o dispositivo continua aberto por outra instância/programa (WinUSB é exclusivo) — inclusive pela própria 0.4.0,
     que fecha o dongle em segundo plano: Desligar/Ligar rápido pode reabrir antes do fechamento terminar;
  3. diferença no carregamento das DLLs (msvcr100/pthreadVC2) no ambiente do usuário.
- **Corrigir:**
  - se a abertura pela DLL Blog falhar (ACCESS, NOT_SUPPORTED etc.), tentar automaticamente a biblioteca padrão
    (a da 0.3.0) e registrar qual abriu; opção em Configurações para escolher a biblioteca (Automático / RTL-SDR Blog / Padrão);
  - ao reabrir, esperar o fechamento anterior terminar (com tempo limite) antes de abrir de novo;
  - mensagem de erro com o diagnóstico (driver da interface 0, biblioteca usada, outro programa usando o dongle);
  - autoteste/CI com um teste que simule falha da DLL Blog e confirme o recurso para a biblioteca padrão.
- **Para investigar com o mantenedor:** captura de Ajuda → Diagnóstico do RTL-SDR (mostra o driver de cada interface
  e a biblioteca carregada) e se algum outro programa SDR estava aberto.

## Concluídos
- 0.4.0 — todos os itens registrados em 07/11/2026: travamento ao mudar de banda (V4) com recuperação automática e
  driver RTL-SDR Blog; auto-sintonizar; modo AUTO; transmissão vizinha ◀▶; modos no display; três níveis de
  interface; waterfall arrastável; painel de áudio sem rolagem; VOX; Configurações + interface web com áudio;
  anúncio ao abrir; OTA e instalador no padrão dos demais programas.
- 0.3.0 — IA/assistente para SSB (auto-sintonia pelos harmônicos da voz, detecção de modo e banda lateral,
  filtro adaptativo, transcrição local opcional), voltar no tempo, receptores extras, instalador/portátil
  Windows e atualização automática pelo www.pt2vhf.com.
- 0.2.0 — memórias prontas, favoritos, scanner por espectro e gravação por atividade.
- 0.1.0 — primeira versão.
