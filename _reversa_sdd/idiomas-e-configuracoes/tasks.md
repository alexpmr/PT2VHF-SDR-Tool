# Idiomas, níveis de interface e configurações, Tarefas de Implementação

## Pré-requisitos
- [ ] Nenhum (infraestrutura base)

## Tarefas

- [ ] T-01, `config_dir` e `Config` com padrões e tolerância a erro
  - Origem no legado: `pt2vhf/config.py:10-103`
  - Critério de pronto: arquivo inválido abre com padrões
  - Confiança: 🟢
- [ ] T-02, `save` atômico (arquivo temporário + `os.replace`)
  - Origem no legado: `pt2vhf/config.py:105-110` (dívida D4)
  - Critério de pronto: interrupção no meio não corrompe o arquivo
  - Confiança: 🟡 (melhoria, não comportamento atual)
- [ ] T-03, Levar todas as chaves usadas para `DEFAULTS`
  - Origem no legado: dívida D8
  - Critério de pronto: nenhum `cfg.get` com padrão divergente
  - Confiança: 🟡
- [ ] T-04, Catálogo e `apply_language` reversível
  - Origem no legado: `pt2vhf/i18n.py:13-162`
  - Critério de pronto: `test_v090_i18n.py` passa; ida e volta restaura textos
  - Confiança: 🟢
- [ ] T-05, `apply_level` por identificador estável em vez de título
  - Origem no legado: `pt2vhf/ui/main_window.py:2282-2305` (dívida D6)
  - Critério de pronto: ocultamento funciona em qualquer idioma
  - Confiança: 🟡
- [ ] T-06, Layout em `QSettings`
  - Origem no legado: `pt2vhf/ui/main_window.py:2193-2200,2348`
  - Critério de pronto: geometria restaurada
  - Confiança: 🟢
- [ ] T-07, Mutex de instância única
  - Origem no legado: `pt2vhf/app.py:29-31`
  - Critério de pronto: instalador detecta programa aberto
  - Confiança: 🟢
- [ ] T-08, `--selftest` com log e código de saída
  - Origem no legado: `pt2vhf/app.py:57-…`
  - Critério de pronto: CI roda o selftest dos dois EXE
  - Confiança: 🟢
