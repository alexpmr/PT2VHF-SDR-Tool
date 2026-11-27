# ERD completo

Não há banco de dados 🟢. As "entidades" são dataclasses em memória, persistidas como JSON, WAV ou log. O ERD abaixo mostra as relações lógicas e onde cada uma é gravada. Detalhes de campos em [data-dictionary.md](data-dictionary.md).

```mermaid
erDiagram
    CONFIG ||--|| MEMORY_BANK : "aponta para memorias.json"
    CONFIG ||--o{ BAND_STACK : "band_stacks por banda"
    MEMORY_BANK ||--o{ CATEGORY : "categories"
    CATEGORY ||--o{ MEMORY_CHANNEL : "category (nome)"
    MEMORY_CHANNEL }o--|| BAND : "band_for(freq), derivado"
    REGION_STORE ||--o{ REGION : "regions por nome"
    REGION ||--o{ MEMORY_CHANNEL : "cópia de canais"
    PRESET_PACK ||--o{ MEMORY_CHANNEL : "importa sem duplicar (categoria + freq/100)"
    SCANNER_CONFIG ||--o{ HIT : "acertos da varredura"
    SCANNER_CONFIG }o--o{ LOCKOUT : "lockouts (set de Hz)"
    SCAN_RANGE ||--|| SCANNER_CONFIG : "preenche"
    OCCUPANCY_HISTORY ||--o{ OCCUPANCY_BIN : "hora x bin 12,5 kHz"
    ACTIVITY_EVENT ||--|| RECORDING_FILE : "file"
    AX25_FRAME ||--|| APRS_PACKET : "parse"
    APRS_PACKET }o--o| TRACK : "posição no mapa APRS"
    TRACK }o--|| TRAFFIC_SOURCE : "ADS-B, AIS, Sonda"
    TLE_SATELLITE ||--o{ LOOK_ANGLE : "propagação SGP4"
    UPDATE_INFO ||--o| PACKAGE_FILE : "file (kind, url, size, sha256)"

    CONFIG {
        string source
        float center_freq
        float vfo_freq
        string mode
        float squelch
        string ui_level
        bool web_require_key
    }
    MEMORY_CHANNEL {
        string id PK "uuid4 hex 10"
        string name
        float freq
        string mode
        float bandwidth
        string category FK
        float ctcss
        bool favorite
        bool skip_scan
    }
    CATEGORY {
        string name PK
    }
    BAND {
        string name PK
        float start
        float end
        string mode
        float step
    }
    REGION {
        string name PK "1 a 100 caracteres"
    }
    HIT {
        float freq PK
        int hits
        float max_snr
        float seconds_active
        bool listened
    }
    OCCUPANCY_BIN {
        int epoch_hora PK
        int freq_bin PK
        int contagem
    }
    ACTIVITY_EVENT {
        string file FK
        float freq
        string mode
        float duration
        float peak_db
    }
    RECORDING_FILE {
        string path PK
        string tipo "AF, IQ, VOX"
    }
    APRS_PACKET {
        string source
        string type
        float lat
        float lon
    }
    TRACK {
        string source
        string ident PK
        float lat
        float lon
        float altitude_m
    }
    UPDATE_INFO {
        string version
        string unavailable_reason
    }
    PACKAGE_FILE {
        string name
        string url
        int size
        string sha256
    }
```

## Persistência

| Entidade | Arquivo | Atômica? | Confiança |
|---|---|---|---|
| CONFIG | `config.json` | ❌ | 🟢 |
| MEMORY_BANK, CATEGORY, MEMORY_CHANNEL | `memorias.json` | ❌; JSON corrompido não é tratado no load | 🟢 |
| REGION_STORE | arquivo de regiões | ✅ | 🟢 |
| OCCUPANCY_HISTORY | `ocupacao_24h.json` | ✅, no máximo 1 vez a cada 20 s | 🟢 |
| HIT, LOCKOUT | Só em memória | — | 🟢 |
| ACTIVITY_EVENT / RECORDING_FILE | WAV na pasta de gravações | Escrita contínua | 🟢 |
| TRACK | Lido de arquivos externos | — | 🟢 |
| UPDATE_INFO | Memória; resultado do auxiliar em `%TEMP%` | — | 🟢 |
