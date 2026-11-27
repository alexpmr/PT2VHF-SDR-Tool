# Fluxogramas — `memory`

> Arqueólogo (Reversa), 2026-11-27. 🟢 extraído de `pt2vhf/memory.py`, `memory_regions.py`, `presets.py`.

## Importação CSV CHIRP

```mermaid
flowchart TD
    A[linha do CSV] --> B{Frequency numérica > 0?}
    B -- não --> X[ignora]
    B -- sim --> C{Mode}
    C -- FM --> C1[NFM 12 kHz]
    C -- NFM --> C2[NFM 8 kHz]
    C -- WFM --> C3[WFM 180 kHz]
    C -- AM --> C4[AM 8 kHz]
    C -- USB/LSB --> C5[2,7 kHz]
    C -- CW --> C6[500 Hz]
    C -- outro --> C7[NFM 12 kHz]
    C1 & C2 & C3 & C4 & C5 & C6 & C7 --> D{Tone ou TSQL?}
    D -- sim --> D1[ctcss = rToneFreq ou cToneFreq]
    D -- não --> E
    D1 --> E[offset pelo Duplex]
    E --> F{categoria}
    F --> F1[parâmetro > coluna Category > Repetidoras se offset > Simplex]
    F1 --> G[adiciona canal, cria categoria se nova]
```

## Importação de pacotes prontos

```mermaid
flowchart LR
    A[chaves escolhidas] --> B[para cada canal dos pacotes]
    B --> C{categoria + freq/100 já existe?}
    C -- sim --> D[pula]
    C -- não --> E[copia com novo id e favorito opcional] --> F[adiciona]
```

## Perfil por região

```mermaid
flowchart TD
    A[nome] --> B{1-100 caracteres sem controle?}
    B -- não --> X[ValueError]
    B -- sim --> C{ação}
    C -- salvar --> D[copia banco atual para regions/nome] --> W[grava JSON atômico]
    C -- importar CHIRP --> E[banco temporário] --> E1{algum canal?}
    E1 -- não --> X2[ValueError]
    E1 -- sim --> D
    C -- carregar --> F{existe?}
    F -- não --> X3[KeyError]
    F -- sim --> G[substitui canais e categorias do banco ativo e salva]
```
