# CAT · Hamlib rigctld, Tarefas de Implementação

## Pré-requisitos
- [ ] `MainWindow.tune`, `set_mode` e `_freq_supported` disponíveis
- [ ] `Config` com `save()`

## Tarefas

- [ ] T-01, `RigCtlClient._cmd` com validação de linha e leitura limitada
  - Origem no legado: `pt2vhf/rigctl.py:28-58`
  - Critério de pronto: recusa CR/LF e >160 caracteres; `RPRT -N` vira `RigCtlError`
  - Confiança: 🟢
- [ ] T-02, `read` e `write` com faixa 1 kHz–10 GHz e mapa de modos
  - Origem no legado: `pt2vhf/rigctl.py:15-19,60-80`
  - Critério de pronto: tabela de `contracts.md` coberta por servidor falso
  - Confiança: 🟢
- [ ] T-03, `RigCtlPanel` com pool de 1 worker e vigia de 300 ms
  - Origem no legado: `pt2vhf/ui/rigctl_panel.py:17-116`
  - Critério de pronto: UI não bloqueia com rigctld fora do ar
  - Confiança: 🟢
- [ ] T-04, Seguir rádio a cada 4 s, só leitura
  - Origem no legado: `pt2vhf/ui/rigctl_panel.py:110-116`
  - Critério de pronto: nenhuma escrita automática
  - Confiança: 🟢
- [ ] T-05, `_cat_received` com faixa e suporte da fonte
  - Origem no legado: `pt2vhf/ui/main_window.py:1523-1534`
  - Critério de pronto: frequência fora da faixa não sintoniza
  - Confiança: 🟢
- [ ] T-06, Persistência `cat_host`, `cat_port`, `cat_auto_sync`
  - Origem no legado: `pt2vhf/ui/rigctl_panel.py:71-75`
  - Critério de pronto: valores sobrevivem a reinício
  - Confiança: 🟢
- [ ] T-07, Teste de regressão "sem PTT"
  - Origem no legado: `pt2vhf/rigctl.py` (ausência de `T`)
  - Critério de pronto: teste falha se surgir comando de transmissão
  - Confiança: 🟡 (teste não existe hoje)
- [ ] T-08, Homologar com transceptor real
  - Origem no legado: —
  - Critério de pronto: leitura e escrita com rádio e rigctld reais
  - Confiança: 🔴
