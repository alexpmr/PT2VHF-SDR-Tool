# Idiomas, níveis de interface e configurações

## Visão Geral
Infraestrutura transversal: configuração persistente em JSON por usuário, tradução parcial da interface para 7 idiomas, níveis de interface (Essencial, Intermediário, Avançado) que só escondem recursos, layout da janela, instância única no Windows e autoteste sem hardware. 🟢

## Responsabilidades
- Carregar, mesclar com padrões e salvar a configuração. 🟢
- Traduzir textos de apresentação por catálogo, com retorno ao PT-BR. 🟢
- Mostrar ou esconder páginas e grupos conforme o nível. 🟢
- Guardar geometria e divisórias da janela. 🟢
- Impedir duas instâncias no Windows. 🟢
- Rodar o autoteste `--selftest`. 🟢

## Regras de Negócio
- Local: `%APPDATA%\PT2VHF-SDR-Tool\config.json` (Windows) ou `$XDG_CONFIG_HOME` / `~/.config/PT2VHF-SDR-Tool/config.json`. 🟢 `config.py:10-15`
- `Config` é um `dict` iniciado com cópia profunda de `DEFAULTS` (70 chaves) e atualizado com o arquivo; JSON inválido ou ilegível é ignorado em silêncio e os padrões valem. `first_run` = arquivo não existia. 🟢 `config.py:94-103`
- `save()` grava UTF-8 indentado direto no arquivo (não atômico) e engole `OSError`. 🟢 `config.py:105-110`. 🟡 Dívida D4: queda no meio da gravação pode corromper o arquivo, que então volta aos padrões.
- Chaves usadas fora de `DEFAULTS` (ex.: `rtl_library`, `vox`, `web_enabled`, `web_allow_lan`, `web_port`, `auto_update`, `igate_*`, `sat_*`) dependem de `cfg.get(chave, padrão)` no ponto de uso. 🟡 Dívida D8.
- Idiomas: pt (Português Brasil), en, es, fr, de, it, zh, com bandeiras desenhadas em vetor. 🟢 `i18n.py:13-21,92`
- Tradução só de apresentação, por catálogo `WORDS` (55 termos); termo ausente fica em português; sem tradutor online. Identificadores internos, modos e títulos de grupo usados na lógica continuam em PT-BR. 🟢 `i18n.py:1-6,83-89`
- `apply_language` guarda o texto original em propriedade do widget e retraduz rótulos, botões, grupos, abas e ações; voltar a pt restaura o original. Mensagem: "Idioma alterado. Partes ainda não traduzidas mantêm o português." 🟢 `i18n.py:127-162`, `ui/main_window.py:520-528`
- Níveis: páginas `tools` 0, `scan` 1, `decode` 1, `extras` 2; grupos "Sintonizador" 0, "Equalizador" 1, "Saída / Gravação" 1, "Assistente de sintonia" 1, "AGC / Ruído" 2, "Voltar no tempo" 2. Nível inválido vira "Avançado" (padrão). Esconder nunca apaga configuração. 🟢 `ui/main_window.py:2282-2305`
- 🟡 Grupos são achados pelo título; como `apply_language` só traduz títulos que estão no catálogo, o ocultamento pode falhar se um desses títulos for traduzido (dívida D6).
- Layout em `QSettings("PT2VHF", "SDRTool")`: `geometry`, `split_v05`, `audio_panel`. 🟢 `ui/main_window.py:2193-2200,2348`
- Windows: mutex `PT2VHF_SDR_Tool_Running`, usado também pelo instalador (AppMutex). 🟢 `app.py:29-31`
- `--selftest`: força offscreen, sem diálogos e sem autoconexão; testa DSP, APRS, assistente e interface com simulador; log em `%TEMP%\pt2vhf-sdr-selftest.log`; código de saída 0 só se tudo passou. 🟢 `app.py:57-75`
- Testes nunca devem sobrescrever a configuração real do operador. 🟢 CLAUDE.md

## Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-01 | Configuração persistente com padrões | Must | Chave ausente assume o padrão |
| RF-02 | Tolerar arquivo corrompido | Must | Abre com padrões, sem travar |
| RF-03 | Trocar idioma em tempo real | Should | Textos do catálogo mudam; resto fica em PT-BR |
| RF-04 | Níveis de interface | Should | Páginas e grupos conforme a tabela |
| RF-05 | Restaurar layout | Could | Geometria igual após reinício |
| RF-06 | Instância única no Windows | Should | Mutex criado |
| RF-07 | Autoteste | Must | `--selftest` sai 0 com cadeia íntegra |

## Requisitos Não Funcionais

| Tipo | Requisito inferido | Evidência no código | Confiança |
|------|--------------------|---------------------|-----------|
| Confiabilidade | Gravação não atômica | `config.py:105-110` | 🟢 |
| Privacidade | Configuração só local | `config.py` | 🟢 |
| Usabilidade | Tradução parcial declarada | `i18n.py:1-6` | 🟢 |

## Critérios de Aceitação

```gherkin
Dado um config.json com JSON inválido
Quando o programa abre
Então usa os padrões e não mostra erro

Dado o idioma English
Quando o operador seleciona no menu
Então os termos do catálogo aparecem em inglês e os demais em português

Dado o idioma English ativo
Quando o operador volta para Português (Brasil)
Então todos os textos originais são restaurados

Dado o nível Essencial
Quando aplicado
Então Scanner, Decodificação e Extras ficam ocultas e "AGC / Ruído" some

Dado ui_level com valor desconhecido no arquivo
Quando o programa abre
Então o nível Avançado é aplicado

Dado uma instalação íntegra
Quando roda --selftest
Então sai com código 0 e grava o log
```

## Prioridade (MoSCoW)

| Requisito | MoSCoW | Justificativa |
|-----------|--------|---------------|
| Configuração, autoteste | Must | Base do programa e do build |
| Idiomas, níveis, mutex | Should | Usabilidade |
| Layout | Could | Conforto |

## Rastreabilidade de Código

| Arquivo | Função / Classe | Cobertura |
|---------|-----------------|-----------|
| `pt2vhf/config.py` | `config_dir`, `DEFAULTS`, `Config` | 🟢 |
| `pt2vhf/i18n.py` | `LANGUAGES`, `WORDS`, `translate`, `flag_icon`, `apply_language` | 🟢 |
| `pt2vhf/ui/main_window.py` | `apply_level`, `LEVELS`, `_language_selected`, `_restore_layout`, `closeEvent` | 🟢 |
| `pt2vhf/ui/settings_panel.py` | `SettingsPanel` (sinal `changed`) | 🟢 |
| `pt2vhf/ui/lcd.py` | `THEMES` | 🟢 |
| `pt2vhf/app.py` | `main`, `selftest`, mutex | 🟢 |
| `tests/test_v090_i18n.py` | idiomas | 🟢 |
