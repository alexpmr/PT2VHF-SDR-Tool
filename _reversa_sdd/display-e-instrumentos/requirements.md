# Display e instrumentos

## Visão Geral
Painel frontal do rádio: LCD de sete segmentos com frequência, modo e S-meter, teclas de banda, medidores analógicos (S e VU), temas, escala e modo apresentação. 🟢

## Responsabilidades
- Exibir a frequência do VFO e aceitar digitação, roda do mouse e teclas. 🟢
- Exibir o S-meter de barras com pico e o estado do squelch. 🟢
- Mostrar teclas de banda só para bandas que o SDR sintoniza. 🟢
- Medidores analógicos opcionais com três estilos. 🟢
- Temas do LCD, escala de 50% a 150% e modo apresentação em tela cheia. 🟢

## Regras de Negócio
- S-meter: dBm = dBFS − 45 + `s_meter_cal`; S9 = −93 dBm; 6 dB por unidade S; acima de S9 mostra "S9+n". 🟢 `dsp/demod.py:177-188`
- Escala de barras de −147 dBm a −33 dBm (S9+60) em 40 segmentos; pico retido por 1,5 s. 🟢 `ui/lcd.py:171-185,355-368`
- Sem medição válida (engine parada ou amostra com mais de 2,5 s), o LCD mostra "S--" e zero barras, nunca barras fixas. 🟢 `ui/lcd.py:171-176`, `ui/main_window.py:2076-2086` (correção do P1 "sete barras vermelhas")
- O indicador de squelch só acende se o squelch estiver ativo (> −150). 🟢 `ui/main_window.py:2082`
- Temas do LCD: Âmbar, Verde, Azul (negativo), Noturno, Branco. 🟢 `ui/lcd.py:19-26`
- Escala preferida do LCD limitada a 50–150% e persistida em `lcd_scale_percent`. 🟢 `ui/lcd.py:108-117`
- Teclas de banda: bandas sem suporte são removidas da grade (5 colunas) e as restantes compactadas; antes de conectar, RTL-SDR sem modelo conhecido gera "Faixa desconhecida". 🟢 `ui/bandkeys.py:68-90`, `ui/main_window.py:924-950`
- Medidores analógicos: S de −147 a −33 dBm e VU de −60 a 0 dB; estilos Valvulado, Militar e Estúdio. 🟢 `ui/analog.py:15-50,130-132`
- Modo apresentação: tela cheia real no monitor atual; no modo mínimo esconde menus, barra de status, cabeçalho, abas, painel de áudio, favoritos e barra do waterfall. 🟢 `ui/main_window.py:2212-2230`
- 🔴 O offset −45 dB é nominal; o S-meter não está calibrado com RF real.

## Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-01 | Mostrar e editar a frequência no LCD | Must | Digitação e roda mudam o VFO (`freqChanged`, `stepRequested`) |
| RF-02 | Teclas de modo no LCD, inclusive AUTO | Must | `modeClicked` |
| RF-03 | S-meter com pico e squelch | Must | Valores conforme a fórmula |
| RF-04 | Ausência de medição explícita | Must | "S--" e zero barras sem amostra recente |
| RF-05 | Teclas de banda filtradas pelo hardware | Must | Bandas fora do alcance não aparecem |
| RF-06 | Teclas ◀ ▶ para transmissão vizinha e A-SINT | Should | `neighborRequested`, `autoTuneToggled` |
| RF-07 | Temas e escala 50–150% | Should | Escala persiste entre sessões |
| RF-08 | Medidores analógicos com 3 estilos | Could | `analog_enabled`, `analog_style` |
| RF-09 | Modo apresentação | Could | `presentation`, `presentation_minimal` |
| RF-10 | Calibração do S-meter | Should | `s_meter_cal` desloca a leitura |

## Requisitos Não Funcionais

| Tipo | Requisito inferido | Evidência no código | Confiança |
|------|--------------------|---------------------|-----------|
| Responsividade | Atualização pelo tick de 33 ms | `ui/main_window.py:_tick` | 🟢 |
| Usabilidade | LCD mantém proporção (`heightForWidth`) | `ui/lcd.py:119-130` | 🟢 |

## Critérios de Aceitação

```gherkin
Dado a engine rodando com sinal a -48 dBFS e calibração 0
Quando o tick atualiza o LCD
Então o LCD mostra -93 dBm e S9

Dado a engine parada
Quando o tick atualiza o LCD
Então o LCD mostra S-- e nenhuma barra acesa

Dado um RTL-SDR R820T conectado
Quando o LCD monta as teclas de banda
Então as bandas de HF abaixo de 24 MHz não aparecem

Dado a escala do LCD em 200%
Quando o valor é aplicado
Então a escala fica em 150%
```

## Prioridade (MoSCoW)

| Requisito | MoSCoW | Justificativa |
|-----------|--------|---------------|
| LCD com frequência, modo e S-meter | Must | Painel principal |
| Teclas de banda filtradas | Must | Evita sintonia impossível |
| Temas, escala, calibração | Should | Conforto e precisão |
| Analógicos, apresentação | Could | Opcionais |

## Rastreabilidade de Código

| Arquivo | Função / Classe | Cobertura |
|---------|-----------------|-----------|
| `pt2vhf/ui/lcd.py` | `LCDDisplay`, `THEMES`, `SEGMENTS`, `meter_segments` | 🟢 |
| `pt2vhf/ui/analog.py` | `NeedleMeter`, `AnalogPanel`, `STYLES`, `PALETTES` | 🟢 |
| `pt2vhf/ui/bandkeys.py` | `BandKeys` | 🟢 |
| `pt2vhf/ui/display_settings.py` | `DisplaySettings`, `ThemeTile` | 🟢 |
| `pt2vhf/dsp/demod.py` | `dbfs_to_s_units` | 🟢 |
| `pt2vhf/ui/main_window.py` | `_tick` (S-meter), `_band_unsupported`, `_set_visible_bands`, `set_presentation` | 🟢 |
