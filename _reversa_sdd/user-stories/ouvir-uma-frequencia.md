# Ouvir uma frequência

**Como** radioamador, **quero** ligar o SDR, sintonizar uma repetidora e ouvir com squelch, **para** acompanhar o QSO sem ruído entre transmissões.

Units: [recepcao-sdr](../recepcao-sdr/requirements.md), [demodulacao-e-audio](../demodulacao-e-audio/requirements.md), [display-e-instrumentos](../display-e-instrumentos/requirements.md), [espectro-e-waterfall](../espectro-e-waterfall/requirements.md), [memorias-e-favoritos](../memorias-e-favoritos/requirements.md).

```gherkin
Dado um RTL-SDR conectado e a fonte "RTL-SDR" selecionada
Quando o operador clica "Ligar", digita 145.500 e escolhe NFM
Então o LCD mostra 145,500 MHz NFM, o waterfall corre e o áudio sai pela placa de som 🟢

Dado o squelch acima do ruído
Quando a repetidora para de transmitir
Então o áudio fecha após a cauda de 0,25 s 🟢

Dado o operador clicando num sinal no waterfall
Quando o clique cai dentro da banda visível
Então o VFO vai para aquele ponto 🟢

Dado o dongle desconectado durante a escuta
Quando o vigia não recebe blocos
Então o estado passa a "recuperando" e, após esgotar as tentativas, pede reconectar e clicar Ligar 🟢
```
Pendência: 🔴 S-meter sem calibração em dBm absoluto.
