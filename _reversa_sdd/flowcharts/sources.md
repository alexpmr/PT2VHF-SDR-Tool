# Fluxogramas — `sources`

> Arqueólogo (Reversa), 2026-11-27. 🟢 extraído de `pt2vhf/sources/`.

## Abertura do RTL-SDR (`RtlSdrSource._default_factory` + `_open`)

```mermaid
flowchart TD
    A[Abrir RTL-SDR #idx] --> B{Fechamentos anteriores pendentes?}
    B -- sim --> B1[join até 3 s cada] --> C
    B -- não --> C{Windows e DLL RTL-SDR Blog embarcada?}
    C -- não --> S[ordem = standard]
    C -- sim --> P{preferência}
    P -- blog --> O1[ordem = blog]
    P -- standard --> S
    P -- auto --> O2[ordem = blog, standard]
    O1 --> L
    O2 --> L
    S --> L[para cada biblioteca da ordem]
    L --> K[_construct: cria RtlSdr]
    K -- erro --> K1{abriu handle USB?}
    K1 -- sim --> K2[rtlsdr_close no handle] --> K3
    K1 -- não --> K3[guarda erro, se blog, marca blog_failed] --> L
    K -- ok --> M{houve erro antes?}
    M -- sim --> M1[aviso: abriu com biblioteca padrão] --> R
    M -- não --> R[define sample_rate]
    L -- sem mais opções --> E{algum erro?}
    E -- não --> E1[SourceError: librtlsdr indisponível]
    E -- sim --> E2{erro contém ACCESS?}
    E2 -- sim --> E3[SourceError: dongle em uso / driver não WinUSB]
    E2 -- não --> E4[SourceError: use Preparar RTL-SDR / Zadig]
    R --> F{centro aceito?}
    F -- não --> F1[centro = 145,5 MHz + aviso] --> G
    F -- sim --> G[aplica ganho, PPM, bias-T, amostragem direta]
    G --> H[lê lista de ganhos] --> Z[pronto]
```

## Vigia e recuperação (`_watch_loop`)

```mermaid
flowchart TD
    A[a cada 250 ms] --> B{comando ocupado > 3 s?}
    B -- sim --> B1[aviso: não respondeu, stalled] --> D
    B -- não --> C{último bloco há > 2 s?}
    C -- não --> C1{status != ok e bloco recente < 0,5 s?}
    C1 -- sim --> C2[status ok, zera falhas, aviso recepção restabelecida] --> A
    C1 -- não --> A
    C -- sim --> D[falhas += 1]
    D --> E{falhas > 3?}
    E -- sim --> E1[status failed, aviso reconectar dongle, para a fonte]
    E -- não --> F[status recovering + aviso tentativa N/3]
    F --> G[_recover: cancela leitura, aguarda até 2,5 s]
    G --> H{leitor antigo terminou?}
    H -- não --> H1[abandona instância travada]
    H -- sim --> H2[fecha em segundo plano, espera 0,3 s]
    H1 --> I[_open novamente]
    H2 --> I
    I -- SourceError --> I1[aviso 1ª linha] --> A
    I -- ok --> J[descarta comandos pendentes, novo leitor] --> A
```

## Mudança de frequência

```mermaid
flowchart LR
    A[set_center_freq hz] --> B{check_freq vazio?}
    B -- não --> B1[aviso ao usuário, retorna False]
    B -- sim --> C[center_freq = hz, enfileira comando freq]
    C --> D[thread rtl-ctl aplica]
    D -- erro --> D1[restaura frequência anterior + aviso]
```

## Preparação de driver no Windows (`rtl_driver.prepare`)

```mermaid
flowchart TD
    A[prepare] --> B[PowerShell Get-PnpDevice VID_0BDA PID_2832/2838]
    B --> C{interface 0 sem WinUSB/libusb?}
    C -- não --> C1[Nada a preparar]
    C -- sim --> D{wdi-simple.exe embarcado?}
    D -- não --> D1[falha: instalador não incluído]
    D -- sim --> E[ShellExecuteEx runas: -t 0 WinUSB, -i 0]
    E -- UAC negado --> E1[falha: cancelado]
    E --> F[aguarda até 180 s]
    F --> G{código 0?}
    G -- sim --> G1[sucesso]
    G -- não --> G2[falha com código]
```
