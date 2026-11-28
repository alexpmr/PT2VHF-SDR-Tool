# Scanner e ocupação

## Visão Geral
Três formas de procurar atividade: o **scanner espectral** (FFT em segmentos, milhares de canais por segundo), a **varredura de memórias/faixa** (canal a canal pelo squelch) e o **histórico de ocupação de 24 h**, que conta em que frequências e horas houve detecções. 🟢

## Responsabilidades
- Varrer uma faixa saltando o centro do SDR e detectar sinais pelo SNR no espectro. 🟢
- Registrar acertos (descoberta) e, opcionalmente, parar para escutar. 🟢
- Checar um canal prioritário periodicamente. 🟢
- Excluir frequências (lockout) e evitar voltar ao mesmo canal logo após escutar (cooldown). 🟢
- Varrer memórias ou uma faixa por passo usando o squelch. 🟢
- Guardar e exibir a ocupação por bin de 12,5 kHz e hora, nas últimas 24 h. 🟢

## Regras de Negócio
- O scanner espectral decide pelo SNR no espectro, não pelo squelch de áudio. 🟢 `scanner.py:1-4`
- Segmento útil = 80% da taxa; faixa que cabe num segmento põe o centro 10 kHz acima do fim (para tirar o DC da faixa) se couber, senão no meio. 🟢 `scanner.py:162-173`
- Durante o scanner, `engine.hold_center = True`: a sintonia não mexe no centro. 🟢 `scanner.py:175`
- Após mudar o centro, descarta `settle_lines` = 2 linhas e acumula `dwell_lines` = 4 linhas em max-hold. Linhas de um centro antigo são ignoradas. 🟢 `scanner.py:126-127,224-232`
- Detecção: piso = mediana dos bins válidos (dentro de 85% da faixa, fora de ±3 kHz do DC, dentro de [início, fim]); sinal = bins acima de piso + `snr_db` (padrão 10 dB); bins a até 2 de distância formam um grupo; a frequência é o centróide de potência, arredondado à `resolution` (padrão 5 kHz). Menos de 8 bins válidos = sem detecção. 🟢 `scanner.py:58-98`
- Acerto existente é casado com tolerância max(1,5 × resolução, largura/3); lockout com tolerância max(resolução, largura/2). 🟢 `scanner.py:187-202`
- Escuta: para no detector de maior SNR fora de lockout e cooldown; mantém enquanto o nível > piso + 0,7 × SNR; retoma após `resume_s` = 2 s sem atividade ou `max_listen_s` (0 = sem limite); cooldown de 8 s por frequência. 🟢 `scanner.py:126-131,248-262,305-314`
- Prioridade: a cada `priority_interval_s` = 3 s, mede o canal prioritário (no segmento atual se couber em 85% da faixa, senão salta para p + fs/8); se ativo, escuta. 🟢 `scanner.py:291-299,316-325`
- Presets de faixa: aviação VHF (AM), marítimo, 2 m, 70 cm, VHF e UHF serviços, FRS, PMR446, PX 11 m, radiossondas, FM broadcast (resolução 100 kHz, WFM, SNR 15) e ondas curtas 49/31/25/19 m (AM, "Requer HF"). 🟢 `scanner.py:21-37`
- Varredura de memórias: exige receptor ligado; se o squelch estiver aberto (≤ −150), aplica o squelch automático e começa 0,7 s depois. Usa a categoria escolhida, ou os favoritos, ou todas, sem os `skip_scan`. 🟢 `ui/main_window.py:1233-1250`
- Varredura de faixa por passo: no máximo 20 000 canais. 🟢 `ui/main_window.py:1251-1256`
- Na varredura de memórias: espera o `dwell`; squelch aberto segura; após fechar, espera `resume` s (0 = fica parado). 🟢 `ui/main_window.py:1270-1291`
- Squelch automático: mede ~0,5 s e põe o limiar 6 dB acima do quartil inferior (o comentário diz mediana). 🟢 `ui/main_window.py:1034-1047`. 🟡 Divergência entre comentário e código.
- Ocupação: só acertos do scanner contam; 1 contagem por minuto por bin de 12,5 kHz; janela de 24 horas; frequência válida 24 kHz–2 GHz; arquivo `ocupacao_24h.json` gravado de forma atômica no máximo a cada 20 s e ao fechar. 🟢 `occupancy.py`, `ui/main_window.py:2053-2069,2358`
- A ocupação mede detecções, não ocupação contínua. 🟢 CHANGELOG 0.7.0

## Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-01 | Scanner espectral de uma faixa com descoberta | Must | Acertos com frequência, SNR e contagem |
| RF-02 | Parar para escutar e retomar | Must | Escuta e retomada conforme `resume_s` |
| RF-03 | Canal prioritário | Should | Checado a cada 3 s |
| RF-04 | Lockout de frequência | Should | Frequência bloqueada some e não volta |
| RF-05 | Presets de faixa | Should | 15 presets disponíveis |
| RF-06 | Varredura de memórias e faixa por passo | Must | Para no squelch aberto |
| RF-07 | Squelch automático | Should | Limiar = quartil inferior + 6 dB |
| RF-08 | Histórico de ocupação 24 h | Should | Matriz hora × frequência, até 80 linhas |
| RF-09 | Limpar a ocupação | Could | `clear()` zera e grava |

## Requisitos Não Funcionais

| Tipo | Requisito inferido | Evidência no código | Confiança |
|------|--------------------|---------------------|-----------|
| Performance | ~640 canais/s a 1,2 MS/s com FFT | CHANGELOG 0.2.0, `scanner.py:channels_per_second` | 🟢 |
| Persistência | Escrita atômica (`.tmp` + `replace`) da ocupação | `occupancy.py:85-100` | 🟢 |
| Limite | Faixa por passo ≤ 20 000 canais | `ui/main_window.py:1253` | 🟢 |

## Critérios de Aceitação

```gherkin
Dado o scanner de 144 a 148 MHz a 2,4 MS/s
Quando ele inicia
Então a faixa é dividida em 3 segmentos de 1,92 MHz e o centro fica preso

Dado um sinal 15 dB acima do piso em 145,5 MHz
Quando o dwell termina
Então surge um acerto em 145,500 MHz

Dado a escuta ligada e um sinal que some
Quando passam 2 s sem atividade
Então o scanner retoma e ignora 145,500 MHz por 8 s

Dado 145,500 MHz em lockout
Quando o sinal aparece de novo
Então nenhum acerto é registrado

Dado o receptor desligado
Quando o operador pede varredura de memórias
Então aparece "Ligue o receptor antes de varrer."

Dado dois acertos em 145,500 MHz no mesmo minuto
Quando a ocupação registra
Então a contagem daquele bin sobe só uma vez
```

## Prioridade (MoSCoW)

| Requisito | MoSCoW | Justificativa |
|-----------|--------|---------------|
| Scanner espectral e escuta | Must | Recurso central (v0.2.0) |
| Varredura de memórias | Must | Uso clássico de scanner |
| Prioridade, lockout, presets | Should | Conforto |
| Ocupação 24 h | Should | Diagnóstico |

## Rastreabilidade de Código

| Arquivo | Função / Classe | Cobertura |
|---------|-----------------|-----------|
| `pt2vhf/scanner.py` | `SpectrumScanner`, `ScannerConfig`, `ScanRange`, `SCAN_PRESETS`, `Hit`, `Detection`, `detect_signals`, `level_at` | 🟢 |
| `pt2vhf/occupancy.py` | `OccupancyHistory`, `BIN_HZ`, `HOURS` | 🟢 |
| `pt2vhf/ui/main_window.py` | `_start_scan`, `_scan_next`, `_scan_tick`, `_stop_scan`, `_auto_squelch`, `_sscan_stop` | 🟢 |
| `pt2vhf/ui/occupancy_panel.py` | painel de ocupação | 🟢 |
| `pt2vhf/ui/listening.py` | `ScannerPanel` (`listening.py:170`) [Revisão: corrigido, o painel do scanner não fica em `panels.py`] | 🟢 |
