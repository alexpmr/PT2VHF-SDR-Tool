# Receber e ver APRS no mapa

**Como** radioamador, **quero** decodificar APRS em 145,570 MHz e ver estações no mapa, **para** acompanhar a atividade local sem TNC.

Units: [aprs-packet](../aprs-packet/requirements.md), [painel-web](../painel-web/requirements.md).

```gherkin
Dado o receptor em 145,570 MHz NFM e o decodificador APRS ligado
Quando chega um quadro AX.25 com FCS válido
Então o pacote aparece na lista e, se tiver posição, no mapa 🟢

Dado um quadro com FCS inválido
Quando é demodulado
Então é descartado sem aparecer 🟢

Dado o painel web ligado
Quando um navegador local abre a página
Então vê os últimos pacotes APRS com texto escapado 🟢
```
O programa só recebe; não há envio ao APRS-IS na interface ([igate-aprs](../igate-aprs/requirements.md) é código órfão). 🟢
