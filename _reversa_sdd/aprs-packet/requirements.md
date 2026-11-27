# APRS e packet

## Visão Geral
Decodifica packet AX.25 em AFSK 1200 bd (Bell 202) a partir do áudio NFM, interpreta os pacotes APRS (posição, Mic-E, clima, mensagens, telemetria, objetos, status) e mostra-os em lista e num mapa HTML só com o que foi recebido. 🟢

## Responsabilidades
- Demodular AFSK 1200 com vários fatiadores e recuperar o relógio (DPLL). 🟢
- Deframar HDLC (NRZI, bit stuffing) e validar o FCS do AX.25. 🟢
- Interpretar o campo de informação APRS. 🟢
- Calcular distância, rumo e locator Maidenhead em relação à estação do operador. 🟢
- Guardar o histórico de posições e exportar um mapa Leaflet. 🟢
- Publicar os últimos pacotes no painel web. 🟢

## Regras de Negócio
- O decoder só roda em NFM e com `decoders.aprs` ligado; recebe o áudio bruto, antes de AGC e squelch. 🟢 `engine.py:403-407`, `dsp/receiver.py:159-168`
- Mark 1200 Hz, space 2200 Hz, 1200 bd; processamento interno a 9600 Hz (8 amostras/bit), passa-faixa 900–2500 Hz e normalização por RMS. 🟢 `decoders/afsk.py:10,24-75`
- Cinco fatiadores com pesos mark−g·space g = 0,5, 0,7, 1,0, 1,4 e 2,0, para compensar a pré-ênfase (técnica do Dire Wolf). 🟢 `decoders/afsk.py:45-46,73-74`
- DPLL: em cada transição a fase é puxada 30% em direção a 0,5. 🟢 `decoders/afsk.py:96-101`
- O mesmo quadro (TNC2 idêntico) recebido por vários fatiadores em menos de 2 s é emitido uma vez; a tabela de duplicados é podada acima de 64 entradas. 🟢 `decoders/afsk.py:48-57`
- AX.25: quadro mínimo de 18 bytes; FCS CRC-16/X.25 obrigatório; até 10 endereços; `*` marca repetido. 🟢 `decoders/ax25.py:72-95`
- Tipos APRS pelo 1º caractere: `! = / @` posição (com carimbo de tempo em `/ @`), `` ` ' `` Mic-E, `>` status, `:` mensagem (PARM./UNIT./EQNS./BITS. = telemetria de definição), `T#` telemetria, `_` clima, `;` objeto, `}` terceiros; senão "Outro". 🟢 `decoders/aprs.py:147-229`
- Posição comprimida (base 91) ou não; `ccc/sss` = rumo e velocidade em nós (convertida para km/h); `/A=` = altitude em pés (convertida para metros). 🟢 `decoders/aprs.py:160-176`
- Símbolo terminado em `_` = estação meteorológica; nesse caso `ccc/sss` vira direção e velocidade do vento. 🟢 `decoders/aprs.py:177-182`
- Erro de interpretação nunca derruba: o texto vai para `comment`. 🟢 `decoders/aprs.py:228-229`
- Mapa: até 150 estações e 40 pontos por estação; descarta a estação mais antiga quando cheio; nome até 20 caracteres, comentário até 120; coordenadas validadas; dados embutidos com escape de `< > &`; centro inicial no Brasil (−15,78, −47,93). 🟢 `aprs_map.py:15-60`
- O mapa só mostra APRS recebido e depende dos tiles do OpenStreetMap e do Leaflet via unpkg. 🟢 `aprs_map.py`
- Texto APRS de terceiros é escapado antes de aparecer na interface web. 🟢 commit 8f3d331
- Nenhum envio ao APRS-IS a partir desta feature (ver `igate-aprs`). 🟢

## Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-01 | Decodificar AFSK 1200 em NFM | Must | Quadro sintético de `afsk_modulate` decodificado |
| RF-02 | Validar FCS e descartar quadros corrompidos | Must | Bit trocado → nenhum evento |
| RF-03 | Interpretar posição, Mic-E, clima, mensagem, telemetria, objeto, status | Must | Campos preenchidos por tipo |
| RF-04 | Lista de pacotes no painel de decodificação | Must | Evento `aprs` aparece com hora |
| RF-05 | Distância e rumo até o locator do operador | Should | `distance_bearing` e `maidenhead` |
| RF-06 | Mapa HTML do recebido | Should | Arquivo `mapa_aprs_recebido.html` |
| RF-07 | Últimos pacotes no painel web | Could | Lista `aprs` no `/state` |

## Requisitos Não Funcionais

| Tipo | Requisito inferido | Evidência no código | Confiança |
|------|--------------------|---------------------|-----------|
| Segurança | Escape de JSON no HTML do mapa | `aprs_map.py:40-42` | 🟢 |
| Segurança | Escape do texto APRS na web | commit 8f3d331 | 🟢 |
| Robustez | Interpretação nunca levanta exceção para a engine | `decoders/aprs.py:228` | 🟢 |

## Critérios de Aceitação

```gherkin
Dado o modo NFM com APRS ligado
Quando chega um quadro AFSK com "PT2XXX>APRS:!2330.00S/04630.00W-Teste"
Então um evento aprs de tipo Posição é emitido com lat -23,5 e lon -46,5

Dado o mesmo quadro detectado por três fatiadores
Quando eles terminam em menos de 2 s
Então só um evento é emitido

Dado um quadro com FCS errado
Quando ele é deframado
Então nenhum evento é emitido

Dado o modo AM
Quando chega o mesmo áudio AFSK
Então o decoder APRS não roda
```

## Prioridade (MoSCoW)

| Requisito | MoSCoW | Justificativa |
|-----------|--------|---------------|
| Demodulação, FCS e interpretação | Must | Núcleo da feature |
| Lista e eventos | Must | Saída para o operador |
| Distância, mapa, web | Should / Could | Complementos |

## Rastreabilidade de Código

| Arquivo | Função / Classe | Cobertura |
|---------|-----------------|-----------|
| `pt2vhf/decoders/afsk.py` | `AFSKDemodulator`, `_Slicer`, `afsk_modulate` | 🟢 |
| `pt2vhf/decoders/ax25.py` | `AX25Frame`, `crc16_x25`, `parse_frame`, `build_frame`, `hdlc_bits`, `nrzi_encode`, `HDLCDeframer` | 🟢 |
| `pt2vhf/decoders/aprs.py` | `APRSPacket`, `parse`, `distance_bearing`, `maidenhead`, `locator_to_latlon` | 🟢 |
| `pt2vhf/aprs_map.py` | `APRSMapHistory` | 🟢 |
| `pt2vhf/engine.py` | `afsk`, `decoders_enabled` | 🟢 |
| `pt2vhf/ui/main_window.py` | tratamento do evento `aprs`, `_web_aprs` | 🟢 |
