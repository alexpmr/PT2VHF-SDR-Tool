# Atualização OTA, Contratos

## Consulta
`GET https://www.pt2vhf.com/update.php?product=sdr&platform=windows-x64&kind=<installer|portable>`
Cabeçalhos: `User-Agent: PT2VHF-SDR-Tool/<versão>`, `Accept: application/json`. Sem redirecionamento. Corpo ≤ 2 000 000 bytes.

```json
{
  "schema": 1,
  "product": "sdr",
  "status": "available",
  "version": "0.13.4",
  "date": "2026-11-20",
  "notes": "…",
  "page": "https://www.pt2vhf.com/sdr",
  "files": [
    {"kind": "installer", "name": "PT2VHF-SDR-Tool-Setup-0.13.4.exe",
     "url": "https://www.pt2vhf.com/downloads/sdr-tool/PT2VHF-SDR-Tool-Setup-0.13.4.exe",
     "size": 123456789, "sha256": "<64 hex minúsculos>"}
  ]
}
```
🟡 Os nomes de arquivo do exemplo são ilustrativos; o código só exige o padrão `[A-Za-z0-9_.-]+.exe`.

| Campo | Regra | Falha |
|---|---|---|
| `schema` | ausente ou 1 | `UpdateError` "Manifesto … inválido" |
| `product` | "sdr" | `UpdateError` |
| `status`, `version` | "available", `^v?\d+\.\d+\.\d+$`, mais nova | `None` (sem novidade) |
| `files[].url` | `is_official` | motivo "URL do pacote incompatível…" |
| `files[].size`, `sha256` | int 1..600 MiB, 64 hex | motivo "Pacote anunciado sem tamanho e SHA-256 válidos." |

## Download
- URL do pacote; redirecionamentos permitidos: site → `https://github.com/alexpmr/PT2VHF-SDR-Tool/releases/download/v<versão>/<nome>` → `release-assets.githubusercontent.com` ou `objects.githubusercontent.com`. Qualquer outro: `UpdateError`.
- `Content-Length`, bytes recebidos e SHA-256 devem bater com o manifesto.

## Auxiliar `apply-update.ps1`
Argumentos: `-WaitPid <pid> -Package <exe> -Destination <pasta> -Executable <exe> -Mode Setup|Portable -Version <X.Y.Z>`.
Resultado em `%TEMP%\PT2VHF-SDR-Tool-update-result.txt`, UTF-8, três linhas:
```
ok|<outro>
<versão>
<detalhe>
```
