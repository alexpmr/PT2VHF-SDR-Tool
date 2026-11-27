# Fluxogramas — `traffic`

> Arqueólogo (Reversa), 2026-11-27. 🟢 extraído de `pt2vhf/traffic.py`, `sonde_rx.py`, `aprs_igate.py`.

## Leitura de feeds externos (`load_traffic`)

```mermaid
flowchart TD
    A[arquivo + tipo] --> B{existe?}
    B -- não --> X[FileNotFoundError]
    B -- sim --> C{AIS?}
    C -- sim --> C1[lê últimos 2 MB] --> C2[descarta 1ª linha parcial se truncou] --> C3[AISDecoder por linha]
    C -- não --> D{> 8 MB?}
    D -- sim --> X2[ValueError: configure rotação]
    D -- não --> E[json.loads]
    E --> F{tipo}
    F -- ADS-B --> F1[parse_adsb]
    F -- Sonda --> F2[parse_radiosondes]
    F -- outro --> X3[ValueError]
```

## Pipeline RS41

```mermaid
flowchart LR
    DSP[thread DSP: iq_listeners] -->|copia, fila 12| W[escritor]
    W --> CH[ChannelIQ: 0 Hz, 48 kS/s, int16]
    CH --> CAP[captura opcional 1-60 s]
    CH --> FSK[fsk_demod stdin]
    FSK -->|pipe| RS[rs41mod]
    RS -->|JSON por linha| R[leitor]
    R --> P{parse_radiosondes tem posição?}
    P -- sim --> EV1[evento sonde_rx]
    P -- não --> EV2[evento sonde_frame]
    FSK -.stderr.-> S[estatísticas / erros -> sonde_status]
    RS -.stderr.-> S
```

## AIS: montagem e decodificação

```mermaid
flowchart TD
    A[linha] --> B{!AIVDM / !AIVDO / !BSVDM?}
    B -- não --> X[ignora]
    B -- sim --> C{checksum presente e errado?}
    C -- sim --> X
    C -- não --> D{campos válidos: count 1-9, fill 0-5?}
    D -- não --> X
    D -- sim --> E{multipartes?}
    E -- sim --> E1[guarda fragmento, > 100 conjuntos limpa tudo]
    E1 --> E2{completo?}
    E2 -- não --> X
    E2 -- sim --> F
    E -- não --> F[bits de 6]
    F --> G{tipo}
    G -- 5 --> G1[nome do navio]
    G -- 1/2/3 --> H[posição classe A]
    G -- 18/19 --> H2[posição classe B]
    G -- outro --> X
    H & H2 --> I{lat/lon disponíveis?}
    I -- não --> X
    I -- sim --> J[Track AIS]
```

## iGate RX-only (`gate_line`)

```mermaid
flowchart TD
    A[TNC2 recebido] --> B{CR/LF/NUL?}
    B -- sim --> X[descarta]
    B -- não --> C{tem ':' e payload não começa com '}'?}
    C -- não --> X
    C -- sim --> D{origem é indicativo válido?}
    D -- não --> X
    D -- sim --> E{caminho com TCPIP/TCPXX/NOGATE/RFONLY/IGATE/GATE/qA*?}
    E -- sim --> X
    E -- não --> F[acrescenta qAO,indicativo]
    F --> G{latin-1 e <= 512 bytes?}
    G -- não --> X
    G -- sim --> H{duplicado em 45 s?}
    H -- sim --> X
    H -- não --> Q[fila 256 -> socket após logresp verified]
```
