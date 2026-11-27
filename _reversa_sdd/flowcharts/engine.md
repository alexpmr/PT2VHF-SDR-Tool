# Fluxogramas — `engine`

> Arqueólogo (Reversa), 2026-11-27. 🟢 extraído de `pt2vhf/engine.py`, `audio.py`, `timeshift.py`.

## Loop da thread DSP

```mermaid
flowchart TD
    A[_loop] --> B[pop_messages da fonte -> eventos source_msg]
    B --> C[read timeout 0,5 s]
    C --> D{bloco?}
    D -- não --> E{fonte parou?}
    E -- sim --> E1[evento error e sai]
    E -- não --> A
    D -- sim --> F[process_block] --> G[atualiza cpu e dropped] --> A
```

## `process_block`

```mermaid
flowchart TD
    A[comandos da UI na fila] --> B[remove DC]
    B --> C{gravando IQ?}
    C -- sim --> C1{iq_vox?}
    C1 -- não --> C2[grava]
    C1 -- sim --> C3{squelch aberto ou < 1,5 s depois?}
    C3 -- sim --> C2
    C --> D[iq_listeners RS41]
    C2 --> D
    C3 -- não --> D
    D --> E{hora de nova linha de waterfall?}
    E -- sim --> E1[compute_spectrum -> spectrum e wf_lines] --> F
    E -- não --> F[timeshift.append]
    F --> G{em replay?}
    G -- sim --> G1[lê do buffer com centro gravado] --> H
    G -- não --> H[Receiver.process]
    H --> I[captura FI para assistente]
    I --> J[mistura até 4 receptores extras]
    J --> K{NFM?}
    K -- sim --> K1[CTCSS] --> K2{tone squelch não confere?}
    K2 -- sim --> K3[silencia]
    K2 -- não --> K4[AFSK + DTMF]
    K3 --> K4
    K -- não --> L
    K4 --> L[status]
    L --> M{RNNoise aceitou?}
    M -- não --> M1[publica áudio: placa, LAN, legendas, gravação]
    M -- sim --> N
    M1 --> N[gravadores VOX e atividade]
```

## `_retune`

```mermaid
flowchart TD
    A[_retune vfo] --> B{fonte não sintonizável ou hold_center?}
    B -- sim --> B1[offset = vfo - centro limitado a 0,95 fs/2]
    B -- não --> C{force ou fora da margem?}
    C -- não --> D[offset = vfo - centro]
    C -- sim --> E[novo centro = vfo + fs/8 se fs >= 900k]
    E --> F{fonte aceitou?}
    F -- não --> B1
    F -- sim --> G[limpa waterfall] --> D
```

## `ActivityRecorder.process`

```mermaid
stateDiagram-v2
    [*] --> Ocioso
    Ocioso --> Ocioso: fechado / guarda pré-gravação 0,5 s
    Ocioso --> Gravando: abriu / novo arquivo + pré-gravação
    Gravando --> Gravando: aberto ou cauda < 1,5 s
    Gravando --> Finalizar: fechado há 1,5 s ou 300 s ou mudou frequência
    Finalizar --> Ocioso: duração >= 1 s -> evento
    Finalizar --> Ocioso: duração < 1 s -> apaga arquivo
```
