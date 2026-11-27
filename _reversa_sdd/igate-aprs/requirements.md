# iGate APRS

## Visão Geral
Ponte receptora RF → APRS-IS. **A interface e o acionamento foram removidos de propósito na v0.10.0** ("nenhum envio APRS-IS pelo receptor"). O módulo `aprs_igate.py` e o painel `ui/igate_panel.py` continuam no repositório sem ligação com a janela, contrariando o pedido do BACKLOG de não deixar componentes órfãos. Esta spec documenta o comportamento do código remanescente. 🟢

## Responsabilidades (código remanescente)
- Validar indicativo e passcode do operador. 🟢
- Converter quadros TNC2 recebidos em linhas APRS-IS com qAO. 🟢
- Filtrar pacotes que não devem ser repassados. 🟢
- Manter conexão com o servidor e enviar por fila, sem bloquear. 🟢

## Regras de Negócio
- Estado atual do produto: sem UI, sem envio. 🟢 CHANGELOG 0.10.0, ADR 012
- Indicativo `[A-Z0-9]{3,7}` com SSID −0 a −15 opcional. 🟢 `aprs_igate.py:17,22-26`
- Passcode de 1 a 5 dígitos informado pelo operador; não há passcode embutido. 🟢 `aprs_igate.py:3-5,75-76`
- Servidor padrão `rotate.aprs2.net:14580`. 🟢 `aprs_igate.py:71`
- Descarta: linha com CR/LF/NUL, sem `:` ou payload, payload de terceiros (`}`), origem inválida, destino inválido, caminho com TCPIP, TCPXX, NOGATE, RFONLY, IGATE, GATE ou `qA*`, linha não latin-1, linha + CRLF > 512 bytes. 🟢 `aprs_igate.py:18,29-65`
- Acrescenta `,qAO,<indicativo>` (RX-only; nunca qAR; sem IS → RF). 🟢 `aprs_igate.py:3,57-58`
- Duplicados descartados por 45 s; fila de 256 linhas; cheia conta `dropped`. 🟢 `aprs_igate.py:19,82,114-133`
- Login `user <call> pass <passcode> vers PT2VHF-SDR <versão>`; aguarda `logresp verified` por até 12 s; recusado espera 15 s; erro de rede espera 5 s. 🟢 `aprs_igate.py:135-177`
- Qualquer reativação exige revisão de segurança e autorização explícita do operador (o produto é prioritariamente receptor). 🟢 CLAUDE.md

## Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-01 | Nenhum envio APRS-IS na UI atual | Must | Nenhum caminho da janela instancia `ReceiveOnlyIGate` |
| RF-02 | Filtros e qAO (código remanescente) | Won't | Testes unitários existentes |
| RF-03 | Remover ou documentar o código órfão | Should | Decisão do mantenedor 🔴 |

## Requisitos Não Funcionais

| Tipo | Requisito inferido | Evidência no código | Confiança |
|------|--------------------|---------------------|-----------|
| Segurança | Sem passcode embutido, validação estrita | `aprs_igate.py:3-5,75` | 🟢 |
| Responsividade | `submit` não espera o socket | `aprs_igate.py:114-133` | 🟢 |
| Disponibilidade | Reconexão com espera de 5 s / 15 s | `aprs_igate.py:158-177` | 🟢 |

## Critérios de Aceitação

```gherkin
Dado a versão atual do programa
Quando o operador recebe pacotes APRS
Então nada é enviado à rede APRS-IS

Dado o código remanescente com indicativo PT2XXX-10
Quando chega "PU2ABC>APRS,WIDE1-1:!2330.00S/04630.00W-"
Então a linha gerada é "PU2ABC>APRS,WIDE1-1,qAO,PT2XXX-10:!2330.00S/04630.00W-"

Dado um pacote com caminho TCPIP*
Quando ele é submetido
Então é descartado
```

## Prioridade (MoSCoW)

| Requisito | MoSCoW | Justificativa |
|-----------|--------|---------------|
| Nenhum envio | Must | Decisão de produto |
| Funcionalidade de iGate | Won't | Removida na v0.10.0 |
| Limpeza do órfão | Should | Pedido do BACKLOG |

## Rastreabilidade de Código

| Arquivo | Função / Classe | Cobertura |
|---------|-----------------|-----------|
| `pt2vhf/aprs_igate.py` | `clean_call`, `gate_line`, `ReceiveOnlyIGate`, `CALLSIGN_RE`, `BLOCKED_PATH`, `SEEN_WINDOW` | 🟢 |
| `pt2vhf/ui/igate_panel.py` | painel órfão | 🟢 |
