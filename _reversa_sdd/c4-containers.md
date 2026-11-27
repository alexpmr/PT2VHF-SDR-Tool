# C4 — Nível 2: Containers

Um único processo Python com várias threads, mais processos auxiliares. Não há banco de dados; a persistência é JSON, WAV e log no diretório de configuração.

```mermaid
flowchart TB
    subgraph proc["Processo PT2VHF SDR Tool (Python 3.12, PyInstaller no Windows)"]
        ui["UI Qt<br/>PySide6 6.11.3 + pyqtgraph<br/>thread principal, tick 33 ms"]
        eng["Engine DSP<br/>thread dedicada, NumPy/SciPy"]
        src["Fontes IQ<br/>threads de leitura, controle e vigia"]
        aud["Saída de áudio<br/>callback PortAudio"]
        ai["Workers de IA<br/>RNNoise e Whisper"]
        web["Servidor HTTP<br/>ThreadingHTTPServer"]
        upd["Verificador OTA<br/>thread de rede"]
        traf["Leitores de tráfego<br/>arquivos externos"]
    end

    store[("Diretório de config<br/>config.json, memorias.json,<br/>ocupacao_24h.json, modelos, log")]
    rec[("Pasta de gravações<br/>WAV AF / IQ / VOX")]
    helper["Auxiliar PowerShell<br/>apply-update.ps1"]
    rs41p["Processos fsk_demod | rs41mod"]
    wdi["wdi-simple.exe<br/>elevado"]

    ui -->|"comandos via fila"| eng
    eng -->|"engine.events + status"| ui
    src -->|"blocos IQ, fila de 32"| eng
    eng -->|"amostras 48 kHz"| aud
    eng -->|"fila de 8 / áudio"| ai
    ai -->|"eventos"| eng
    eng -->|"PCM 16 kHz, fila 40 por ouvinte"| web
    eng -->|"IQ canalizado"| rs41p
    ui --> upd
    upd -->|"inicia e fecha o app"| helper
    ui --> traf
    ui --> wdi
    ui <--> store
    eng --> rec
```

| Container | Tecnologia | Responsabilidade | Confiança |
|---|---|---|---|
| UI Qt | PySide6, pyqtgraph | Janela, LCD, waterfall, painéis; dona exclusiva dos widgets | 🟢 |
| Engine DSP | NumPy/SciPy, thread | Demodulação, squelch, decoders, gravação, timeshift, extras | 🟢 |
| Fontes IQ | pyrtlsdr, socket, SoapySDR, WAV, simulador | Aquisição e recuperação do dongle | 🟢 |
| Saída de áudio | sounddevice | Buffer com prime de 150 ms | 🟢 |
| Workers de IA | pyrnnoise, faster-whisper | Redução de ruído, legendas e transcrição fora da thread RF | 🟢 |
| Servidor HTTP | `http.server` | Painel web somente leitura | 🟢 |
| Verificador OTA | `urllib` | Manifesto, download e verificação SHA-256 | 🟢 |
| Auxiliar PowerShell | `apply-update.ps1` | Substitui o executável após o app fechar | 🟢 código, 🔴 campo |
| fsk_demod + rs41mod | Binários externos | Demodulação e decodificação RS41 | 🔴 RF real |
| wdi-simple | libwdi | Instala WinUSB com um UAC | 🟢 (sem testes) |
