# Acompanhar uma radiossonda RS41

**Como** caçador de sondas, **quero** decodificar uma RS41 e ver serial, posição e altitude, **para** localizar o pouso.

Units: [radiossonda-rs41](../radiossonda-rs41/requirements.md), [trafego-adsb-ais](../trafego-adsb-ais/requirements.md).

```gherkin
Dado o receptor ligado, fsk_demod e rs41mod indicados pelo operador
Quando o operador inicia a decodificação em 403 MHz
Então o programa envia IQ de 48 kS/s às ferramentas externas e mostra os quadros JSON 🟢 (código)

Dado os binários ausentes
Quando o operador tenta iniciar
Então vê o aviso de binários não encontrados e nada é baixado 🟢

Dado uma sonda real no ar
Quando a decodificação roda
Então serial, posição e altitude aparecem no mapa 🔴 (nunca demonstrado com RF real, P0)
```
