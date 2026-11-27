# Assistente de sintonia

## Visão Geral
Analisa o IQ em torno do VFO para detectar o modo (AUTO), corrigir a sintonia fina (A-SINT, inclusive SSB pela voz), ajustar o filtro ao sinal e pular para a transmissão vizinha. Sempre corrige o VFO, nunca o áudio. 🟢

## Responsabilidades
- Capturar alguns segundos de IF de 240 kHz centrado no VFO sem bloquear a DSP. 🟢
- Classificar o modo pelo espectro e pela envoltória. 🟢
- Estimar o erro de sintonia de SSB pelos harmônicos da voz. 🟢
- Achar a portadora ou o centro do sinal e encaixar no canal do passo. 🟢
- Sugerir bordas de filtro adaptadas ao sinal. 🟢
- Saltar para o próximo sinal ativo à esquerda ou à direita. 🟢

## Regras de Negócio
- Captura: `capture_if(segundos)` guarda o IF de 240 kHz e chama o callback numa thread separada. 🟢 `engine.py:283-289,377-386`
- AUTO captura 2,5 s; A-SINT 4 s em SSB e 0,6 s nos demais; a captura começa 250 ms depois da seleção. 🟢 `ui/main_window.py:1650-1666`
- Resultado é descartado se outra seleção aconteceu ou o VFO mudou mais de 1 Hz durante a análise. 🟢 `ui/main_window.py:1669-1670`
- Detecção de modo (`detect_mode`): 🟢 `dsp/assist.py:184-236`
  - largura ocupada > 60 kHz → WFM (largura 150–200 kHz, confiança 0,9);
  - < 3 kHz, manipulado > 15% e (portadora > 20% ou < 700 Hz) → CW 0,85; < 700 Hz → CW 0,6;
  - CV da envoltória < 0,35 e 3–30 kHz → NFM (12 kHz se > 7 kHz, senão 8 kHz) 0,85;
  - portadora > 25% e simétrica → AM 0,8;
  - 1,2–4,5 kHz sem portadora → USB/LSB pelos harmônicos (0,8) ou pela convenção da faixa (USB ≥ 10 MHz) 0,5;
  - ≤ 30 kHz e CV < 0,5 → NFM 0,5; senão AM 0,4.
- AUTO só aplica com confiança ≥ 0,55; arredonda o alvo a 10 Hz (CW), 1 Hz (SSB) ou 100 Hz (demais); se AUTO + A-SINT e o modo for NFM/WFM/AM, roda a sintonia fina em seguida. 🟢 `ui/main_window.py:1674-1684`
- Sintonia fina (`fine_tune`): SSB por `estimate_ssb_offset` (até ±600 Hz); AM/CW pelo pico com interpolação parabólica; NFM/WFM/DSB pelo centro do sinal; busca ±1,5 kHz (CW), ±6 kHz (AM), ±120 kHz (WFM), ±15 kHz (demais); com passo ≥ 2,5 kHz encaixa no canal se a diferença ≤ 30% do passo. 🟢 `dsp/assist.py:278-310`
- Correção menor que 2 Hz (SSB/CW) ou 20 Hz (demais) é ignorada. 🟢 `ui/main_window.py:1687-1688`
- Filtro adaptativo: margem 150 Hz (SSB/CW) ou 600 Hz; USB 100–4000 Hz, LSB −4000..−100 Hz, CW 100–1000 Hz, AM ≥ 2,5 kHz, NFM ≥ 4 kHz, WFM ≥ 50 kHz, limite 15 kHz (100 kHz em WFM). 🟢 `dsp/assist.py:239-257`
- Vizinho: usa o último espectro do centro atual; resolução entre 500 Hz e 5 kHz; SNR 10 dB; distância mínima max(0,6 × largura, 1,5 kHz); ignora lockouts do scanner; sem receptor ligado mostra aviso. 🟢 `ui/main_window.py:1715-1740`

## Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-01 | Modo AUTO ao selecionar uma transmissão | Should | Modo e frequência aplicados com confiança ≥ 0,55 |
| RF-02 | A-SINT (sintonia fina) | Should | Correção aplicada acima do limiar |
| RF-03 | Auto-sintonia SSB pela voz | Should | Erro de ±600 Hz corrigido |
| RF-04 | Ajustar filtro ao sinal | Could | Bordas sugeridas aplicadas |
| RF-05 | Transmissão vizinha ◀ ▶ | Should | Sintoniza o sinal mais próximo no sentido pedido |
| RF-06 | Descartar análise obsoleta | Must | Resultado ignorado se o VFO mudou |

## Requisitos Não Funcionais

| Tipo | Requisito inferido | Evidência no código | Confiança |
|------|--------------------|---------------------|-----------|
| Responsividade | Análise em thread separada; resultado volta por evento | `engine.py:386`, `ui/main_window.py:1659-1665` | 🟢 |
| Segurança de operação | Correção no VFO, não no áudio (ADR 004) | `dsp/assist.py:1-7` | 🟢 |

## Critérios de Aceitação

```gherkin
Dado uma portadora NFM 3 kHz acima do VFO
Quando o operador seleciona a transmissão com AUTO ligado
Então o modo vira NFM e o VFO é corrigido em cerca de +3 kHz

Dado uma voz USB 200 Hz desafinada
Quando o operador pede Auto-sintonia SSB
Então o VFO é corrigido em cerca de +200 Hz

Dado uma análise em andamento
Quando o operador sintoniza outra frequência
Então o resultado da análise antiga é descartado

Dado o receptor desligado
Quando o operador aperta ▶
Então aparece "Ligue o receptor para procurar transmissões."
```

## Prioridade (MoSCoW)

| Requisito | MoSCoW | Justificativa |
|-----------|--------|---------------|
| Descartar análise obsoleta | Must | Evita sintonia errada |
| AUTO, A-SINT, vizinho | Should | Com alternativa manual |
| Filtro adaptativo | Could | Ajuste fino |

## Rastreabilidade de Código

| Arquivo | Função / Classe | Cobertura |
|---------|-----------------|-----------|
| `pt2vhf/dsp/assist.py` | `estimate_ssb_offset`, `ModeGuess`, `occupied_band`, `detect_mode`, `adaptive_passband`, `fine_tune` | 🟢 |
| `pt2vhf/engine.py` | `capture_if` | 🟢 |
| `pt2vhf/ui/assist_panels.py` | `AssistBox` | 🟢 |
| `pt2vhf/ui/main_window.py` | `_after_select`, `_auto_result`, `_after_select_tune_only`, `jump_neighbor` | 🟢 |
