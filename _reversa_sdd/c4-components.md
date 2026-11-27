# C4 — Nível 3: Componentes

Componentes dos dois containers centrais: **Engine DSP** e **UI Qt**. Os módulos de domínio estão em `pt2vhf/`.

## Engine DSP

```mermaid
flowchart LR
    subgraph engine["Engine (pt2vhf/engine.py)"]
        loop["Loop DSP<br/>_run / _process"]
        cmdq["Fila de comandos<br/>executa entre blocos"]
        retune["Retune<br/>centro = VFO + fs/8"]
        rx["Receiver principal<br/>dsp/receiver.py"]
        extras["Receptores extras<br/>até 4"]
        sq["Squelch + tone squelch<br/>dsp/demod.py"]
        dec["Decoders<br/>AFSK/AX.25/APRS, DTMF, CTCSS"]
        ts["TimeShiftBuffer<br/>timeshift.py"]
        recs["Gravadores<br/>WavRecorder, ActivityRecorder"]
        nn["NeuralDenoiser<br/>neural_audio.py"]
        cap["LiveCaption / Transcriber"]
        sonde["RS41Receiver<br/>sonde_rx.py"]
        events["engine.events<br/>Queue de tuplas"]
    end
    src["Fonte IQ"] --> loop
    cmdq --> loop
    loop --> retune
    loop --> ts
    loop --> rx
    loop --> extras
    loop --> sonde
    rx --> sq
    rx -->|"áudio bruto NFM"| dec
    sq --> recs
    sq --> nn
    nn --> out["AudioOutput"]
    nn --> cap
    dec --> events
    recs --> events
    cap --> events
    sonde --> events
```

## UI Qt

```mermaid
flowchart LR
    subgraph ui["UI (pt2vhf/ui/)"]
        mw["MainWindow<br/>main_window.py, 2371 linhas"]
        lcd["LCD + medidores<br/>lcd.py, analog.py"]
        wf["Waterfall / espectro<br/>waterfall.py"]
        bands["BandKeys<br/>bandkeys.py"]
        panels["Painéis de memória, scanner,<br/>decodificação, ferramentas<br/>panels.py, listening.py"]
        assist["Assistente, timeshift, extras,<br/>UpdateController<br/>assist_panels.py"]
        occ["Ocupação 24 h<br/>occupancy_panel.py"]
        traf["Tráfego e sondas<br/>traffic_panel.py, sonde_decoder_panel.py"]
        cat["CAT<br/>rigctl_panel.py"]
        capp["Legendas<br/>live_captions_panel.py"]
        cfgp["Configurações e display<br/>settings_panel.py, display_settings.py"]
        orphan["Órfãos: igate_panel.py,<br/>satellite_panel.py fora das abas"]
    end
    mw --> lcd & wf & bands & panels & assist & occ & traf & cat & capp & cfgp
    mw -->|"comandos"| eng["Engine"]
    eng -->|"eventos no tick 33 ms"| mw
    mw --> scan["SpectrumScanner<br/>scanner.py"]
    mw --> mem["MemoryBank / Regiões / Presets"]
    mw --> websrv["WebServer"]
    mw --> cfg["Config"]
```

| Componente | Responsabilidade | Observação |
|---|---|---|
| `MainWindow` | Orquestra tudo: sintonia, níveis, OTA, web, scanner, eventos | 🟡 God object; concentra ~11% do código |
| `SpectrumScanner` | Varredura FFT com estados | Chama `engine.tune` diretamente 🟢 |
| `UpdateController` | Fluxo OTA na UI | Adia quando `operation_busy()` 🟢 |
| `RS41Receiver` | Pipes para binários externos | 🔴 RF real |
| `aprs_igate.ReceiveOnlyIGate`, `igate_panel` | Sem uso | 🟢 órfão desde v0.10.0 |
| `SatellitePanel` | Biblioteca orbital preservada | 🟢 fora das abas |
