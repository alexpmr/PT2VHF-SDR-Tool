# Atualizar o programa

**Como** operador no Windows, **quero** que o programa se atualize sozinho quando estiver livre, **para** não ter de baixar instaladores à mão.

Units: [atualizacao-ota](../atualizacao-ota/requirements.md), [idiomas-e-configuracoes](../idiomas-e-configuracoes/requirements.md).

```gherkin
Dado o instalador Windows e uma versão nova publicada no site oficial
Quando a verificação roda 12 s após abrir
Então o pacote é baixado, conferido por tamanho e SHA-256 e instalado, e o programa reabre 🔴 (não homologado no Windows real)

Dado uma gravação em andamento
Quando há versão nova
Então a instalação é adiada e tentada de novo a cada 60 s 🟢

Dado o pacote com hash divergente
Quando o download termina
Então nada é instalado e o arquivo é apagado 🟢

Dado a execução pelo código-fonte
Quando o operador verifica
Então é orientado a atualizar pelo gerenciador de versões 🟢
```
