# Painel web, Contratos

## Autenticação
| Origem | Condição | Resultado |
|---|---|---|
| Loopback | sempre | autorizado, sem cookie |
| Qualquer, LAN desligada | não loopback | 403 |
| IP privado, LAN ligada, chave dispensada | — | autorizado |
| Qualquer, LAN ligada | `?key=<chave>` igual | autorizado + `Set-Cookie: PT2VHFSDR=<chave>; HttpOnly; SameSite=Strict; Path=/` |
| Qualquer, LAN ligada | cookie `PT2VHFSDR` igual | autorizado |
| Demais | — | 403 `text/plain` |

## Cabeçalhos comuns
`Content-Type`, `Content-Length`, `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`. Protocolo HTTP/1.1.

## `GET /state` → `application/json`
```json
{
  "version": "0.13.3",
  "freq": 145500000.0,
  "mode": "NFM",
  "bw": 12000.0,
  "s_text": "S9",
  "dbm": -93.0,
  "sq_open": true,
  "ctcss": 88.5,
  "mem": "Repetidora",
  "scan": false,
  "replay": false,
  "running": true,
  "aprs": [{"t": "12:34:56", "src": "PU2ABC", "type": "Posição", "pos": "…", "text": "…"}],
  "listeners": 1
}
```
`ctcss` pode ser `null`. `aprs` traz os últimos pacotes (texto até 80 caracteres). 🟢

## `GET /spectrum` → `application/json` ou 204
```json
{"c": 145800000.0, "fs": 2400000, "db": [-98.2, -97.9]}
```
`db` com até ~1024 valores (máximo por grupo), 0,1 dB. 🟢

## `GET /audio` → `application/octet-stream`, chunked
- `X-Audio-Format: s16le;rate=16000;channels=1`
- Chunks de PCM; sem áudio por 1 s, 1600 amostras de silêncio.
- Termina quando o servidor para ou o cliente fecha. 🟢
