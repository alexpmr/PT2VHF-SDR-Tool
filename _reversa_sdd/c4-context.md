# C4 — Nível 1: Contexto

O PT2VHF SDR Tool é um **receptor SDR desktop** de um único operador. Ele não transmite RF e não envia áudio para fora da máquina, salvo pelo painel web local ou da LAN.
Escala: 🟢 confirmado · 🟡 inferido · 🔴 lacuna.

```mermaid
flowchart TB
    op["Operador radioamador<br/>(pessoa)"]
    lan["Ouvinte no navegador<br/>(loopback ou LAN)"]

    subgraph sistema["PT2VHF SDR Tool"]
        app["Aplicativo desktop Python + Qt<br/>recepção, demodulação, decodificação"]
    end

    sdr["Hardware SDR<br/>RTL-SDR / V4 via USB"]
    rtltcp["Servidor rtl_tcp<br/>(rede)"]
    soapy["Drivers SoapySDR"]
    audio["Placa de som<br/>PortAudio"]
    ext["Decoders externos<br/>dump1090/readsb, NMEA AIS"]
    rs41["Binários fsk_demod + rs41mod"]
    rig["Hamlib rigctld<br/>TCP 4532"]
    site["Site www.pt2vhf.com<br/>manifesto OTA e pacotes"]
    gh["GitHub Releases<br/>destino de redirect do pacote"]
    hf["Repositório de modelos Whisper<br/>via faster-whisper"]
    osm["Leaflet / OpenStreetMap<br/>(no navegador)"]
    win["Windows: UAC + libwdi<br/>driver WinUSB"]
    aprsis["APRS-IS<br/>(código órfão, sem UI)"]

    op -->|"usa a janela"| app
    lan -->|"HTTP GET somente leitura"| app
    sdr -->|"IQ via librtlsdr"| app
    rtltcp -->|"IQ via TCP"| app
    soapy -->|"IQ"| app
    app -->|"áudio PCM"| audio
    ext -->|"arquivos JSON/NMEA locais"| app
    app -->|"IQ 48 kS/s por pipe"| rs41
    rs41 -->|"quadros JSON"| app
    app -->|"comandos f, m, F, M"| rig
    app -->|"HTTPS manifesto + pacote SHA-256"| site
    site -.->|"redirect restrito"| gh
    app -->|"download explícito"| hf
    app -->|"HTML do mapa APRS"| osm
    app -->|"um UAC para WinUSB"| win
    app -.->|"desligado"| aprsis
```

| Elemento | Relação | Protocolo | Confiança |
|---|---|---|---|
| Operador | Opera tudo pela UI Qt | Local | 🟢 |
| Ouvinte web | Lê estado, espectro e áudio | HTTP GET, porta 8095 | 🟢 |
| RTL-SDR | Fonte IQ principal | USB, librtlsdr (Blog ou padrão) | 🟢 |
| rtl_tcp | Fonte IQ remota | TCP | 🟢 |
| SoapySDR | Fonte IQ genérica | Biblioteca nativa | 🟢 (sem testes) |
| PortAudio | Saída de áudio | sounddevice | 🟢 |
| dump1090/readsb, AIS | Tráfego por arquivo | JSON, NMEA | 🟢 |
| fsk_demod/rs41mod | Decodificação RS41 | stdin/stdout | 🟢 código, 🔴 RF real |
| rigctld | CAT sem PTT | TCP texto Hamlib | 🟢 |
| www.pt2vhf.com | OTA | HTTPS, SHA-256 | 🟢 código, 🔴 campo |
| GitHub Releases | Hospedagem do pacote | HTTPS redirect restrito | 🟢 |
| Modelos Whisper | Download sob demanda | HTTPS via `faster_whisper.utils.download_model` | 🟡 origem (Hugging Face) inferida da biblioteca |
| Leaflet/OSM | Mapa no navegador | HTTPS (unpkg, tile.openstreetmap.org) | 🟢 |
| Windows UAC/libwdi | Driver WinUSB | ShellExecute `runas` | 🟢 |
| APRS-IS | Sem uso na UI | TCP 14580 | 🟢 órfão |
