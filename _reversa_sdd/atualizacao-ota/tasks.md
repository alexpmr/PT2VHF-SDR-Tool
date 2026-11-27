# Atualização OTA, Tarefas de Implementação

## Pré-requisitos
- [ ] Contrato `update.php` publicado pelo site (fora deste repositório)
- [ ] `MainWindow.operation_busy` e `quit_for_update`

## Tarefas

- [ ] T-01, `install_kind`
  - Origem no legado: `pt2vhf/updater.py:64-72`
  - Critério de pronto: três tipos detectados em teste
  - Confiança: 🟢
- [ ] T-02, `is_official` e `select_update` com motivos
  - Origem no legado: `pt2vhf/updater.py:75-158`
  - Critério de pronto: tabela de `contracts.md` coberta
  - Confiança: 🟢
- [ ] T-03, `check` sem redirecionamento e limite de 2 MB
  - Origem no legado: `pt2vhf/updater.py:161-179`
  - Critério de pronto: redirecionamento vira `UpdateError`
  - Confiança: 🟢
- [ ] T-04, `download` verificado e `_PackageRedirect`
  - Origem no legado: `pt2vhf/updater.py:101-127,182-220`
  - Critério de pronto: `test_ota_site_release_redirect.py` passa; hash errado apaga o arquivo
  - Confiança: 🟢
- [ ] T-05, `apply` e auxiliar PowerShell
  - Origem no legado: `pt2vhf/updater.py:223-255`, `scripts/apply-update.ps1`
  - Critério de pronto: Setup e Portable instalam e reabrem
  - Confiança: 🔴 (não homologado)
- [ ] T-06, `UpdateController`: automático, adiamento, soneca, falha
  - Origem no legado: `pt2vhf/ui/assist_panels.py:196-377`
  - Critério de pronto: 60 s, 6 h e 24 h respeitados; sem navegador
  - Confiança: 🟢
- [ ] T-07, Resultado da atualização anterior
  - Origem no legado: `pt2vhf/updater.py:258-270`, `pt2vhf/ui/assist_panels.py:379-391`
  - Critério de pronto: mensagem e arquivo apagado
  - Confiança: 🟢
- [ ] T-08, Resolver `check_updates` × `auto_update`
  - Origem no legado: `pt2vhf/config.py:83`, `pt2vhf/ui/assist_panels.py:284`
  - Critério de pronto: uma única chave documentada em DEFAULTS
  - Confiança: 🟡
- [ ] T-09, Homologar no Windows real (instalador e portátil)
  - Origem no legado: BACKLOG P0
  - Critério de pronto: atualização de vN para vN+1 pelo site, com log
  - Confiança: 🔴
