# Seguir o transceptor pelo CAT

**Como** radioamador com um transceptor, **quero** que o SDR acompanhe a frequência do rádio, **para** ver no waterfall o que estou ouvindo nele.

Units: [cat-rigctl](../cat-rigctl/requirements.md).

```gherkin
Dado o rigctld rodando com o modelo do rádio
Quando o operador marca "Seguir automaticamente"
Então a cada 4 s o SDR lê frequência e modo e se sintoniza 🟢

Dado o rigctld fora do ar
Quando a leitura falha
Então o status mostra o erro e a interface continua responsiva 🟢

Dado qualquer uso do CAT
Quando o programa se comunica com o rádio
Então nunca aciona PTT 🟢
```
Pendência: 🔴 não testado com transceptor real.
