# Idiomas, níveis de interface e configurações, Design Técnico

## Interface

| Símbolo | Assinatura | Retorno | Observação |
|---------|-----------|---------|------------|
| `config_dir` | `()` | `Path` | Por sistema operacional |
| `Config` | `(path=None)` | `dict` | `save()`, `first_run`, `path` |
| `translate` | `(text, code)` | `str` | Código desconhecido = pt |
| `apply_language` | `(root, code)` | `None` | Guarda original em propriedades `_original_*` |
| `flag_icon` | `(country)` | `QIcon` | Vetorial |
| `MainWindow.apply_level` | `(name)` | `None` | Grava `ui_level` |
| `selftest` | `()` | `int` | 0 = ok |

## Fluxo Principal
1. `app.main` trata `--selftest`, cria o mutex (Windows), cria `Config` e a janela. 🟢
2. A janela aplica `ui_level` e o idioma salvo, restaura o layout. 🟢
3. Mudanças de configuração chegam por `SettingsPanel.changed(chave, valor)` → `_setting_changed` grava em `cfg` e aplica efeitos. 🟢 `ui/main_window.py:1536`
4. Ao fechar, salva layout em `QSettings` e `cfg.save()`. 🟢

## Fluxos Alternativos
- **Arquivo inválido:** padrões. 🟢
- **Disco sem permissão:** `save` falha em silêncio. 🟡 O operador não é avisado.
- **Idioma sem termo:** mantém PT-BR. 🟢

## Decisões de design
- Catálogo local em vez de tradução online (privacidade e operação offline). 🟢
- Níveis escondem em vez de desligar, para nunca perder configuração. 🟢

## Lacunas
- 🟡 D4 gravação não atômica; D6 títulos PT-BR como chave; D8 chaves fora de DEFAULTS.
- 🟡 Cobertura de tradução parcial (55 termos) não é medida.
