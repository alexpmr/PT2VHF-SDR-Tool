# Fluxogramas — `decoders`

> Arqueólogo (Reversa), 2026-11-27. 🟢 extraído de `pt2vhf/decoders/`.

## APRS: áudio até pacote

```mermaid
flowchart LR
    A[áudio FM bruto 48 kHz] --> B[Decima para 9600 Hz]
    B --> C[PF 900-2500 Hz] --> D[normaliza RMS]
    D --> E[correlação mark 1200 / space 2200]
    E --> F1[fatiador g=0,5]
    E --> F2[g=0,7]
    E --> F3[g=1,0]
    E --> F4[g=1,4]
    E --> F5[g=2,0]
    F1 & F2 & F3 & F4 & F5 --> G[DPLL + NRZI]
    G --> H[HDLC: flags, destuffing, abort]
    H --> I{FCS CRC-16 X.25 ok?}
    I -- não --> X[descarta]
    I -- sim --> J{mesmo TNC2 há < 2 s?}
    J -- sim --> X
    J -- não --> K[on_frame -> aprs.parse]
```

## `aprs.parse` por tipo de dado

```mermaid
flowchart TD
    A[info] --> B{1º caractere}
    B -- "! = / @" --> P[Posição, pula timestamp em / @]
    P --> P1{dígito?}
    P1 -- sim --> P2[não comprimida]
    P1 -- não --> P3[comprimida base 91]
    P2 & P3 --> P4[ccc/sss e /A=]
    P4 --> P5{símbolo termina em _?}
    P5 -- sim --> WX[Clima, ccc/sss vira vento]
    P5 -- não --> POS[Posição]
    B -- "` ' 0x1c 0x1d" --> MIC[Mic-E]
    B -- ">" --> ST[Status]
    B -- ":" --> MSG{PARM/UNIT/EQNS/BITS?}
    MSG -- sim --> TD[Telemetria def.]
    MSG -- não --> M[Mensagem sem id]
    B -- "T#" --> TL[Telemetria]
    B -- "_" --> WX2[Clima posicional]
    B -- "," --> OBJ[Objeto]
    B -- "}" --> TP[Terceiros]
    B -- outro --> OUT[Outro]
```

## DTMF por quadro

```mermaid
flowchart TD
    A[quadro 205 amostras a 8 kHz] --> B[Goertzel 4 baixos + 4 altos]
    B --> C{tons > 60% da energia?}
    C -- não --> N[sem tecla]
    C -- sim --> D{2º de cada grupo < 15%?}
    D -- não --> N
    D -- sim --> E{twist entre -8 e 8 dB?}
    E -- não --> N
    E -- sim --> K[tecla candidata]
    K --> F{igual ao quadro anterior?}
    F -- sim --> G{contagem >= 2 e ainda não emitida?}
    G -- sim --> EMIT[on_digit]
    F -- não --> R[reinicia contagem]
    N --> R
```
