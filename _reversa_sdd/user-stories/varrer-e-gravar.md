# Varrer uma faixa e gravar o que aparecer

**Como** escuta, **quero** varrer uma faixa, parar em atividade e gravar cada transmissão, **para** revisar depois o que passou.

Units: [scanner-e-ocupacao](../scanner-e-ocupacao/requirements.md), [gravacao-e-timeshift](../gravacao-e-timeshift/requirements.md), [legendas-e-transcricao](../legendas-e-transcricao/requirements.md).

```gherkin
Dado uma faixa com passo, piso e SNR configurados
Quando o operador inicia o scanner
Então ele percorre os segmentos e para em sinal acima de piso + SNR fora de lockout 🟢

Dado a gravação por atividade ligada
Quando o squelch abre
Então cria um WAV com 0,5 s de pré-gravação e fecha 1,5 s após o squelch fechar 🟢

Dado uma transmissão de menos de 1 s
Quando a gravação termina
Então o arquivo é descartado 🟢

Dado que o operador perdeu o começo de uma chamada
Quando usa "Voltar no tempo" 10 s
Então ouve o trecho do buffer e volta ao vivo ao alcançar o presente 🟢
```
