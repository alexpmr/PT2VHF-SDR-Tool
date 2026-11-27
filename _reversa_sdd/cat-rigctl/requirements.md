# CAT · Hamlib rigctld

## Visão Geral
Cliente TCP do Hamlib `rigctld` que lê frequência e modo de um transceptor externo para sintonizar o SDR, ou envia frequência e modo do SDR para o rádio. **Nunca aciona PTT nem transmite.** O programa é sempre cliente; não abre porta. 🟢

## Responsabilidades
- Ler frequência (`f`) e modo (`m`) do rádio e sintonizar o SDR. 🟢
- Enviar frequência (`F`) e modo (`M`) do SDR ao rádio. 🟢
- Seguir o rádio automaticamente a cada 4 s, se o operador ligar. 🟢
- Fazer a rede fora da thread da interface. 🟢

## Regras de Negócio
- Host padrão `127.0.0.1`, porta padrão 4532 (1–65535), timeout 1,5 s. Host vazio ou porta inválida: `ValueError`. 🟢 `rigctl.py:21-26`
- Só quatro comandos existem: `f`, `m`, `F <hz>`, `M <modo> 0`. Não há comando `T` (PTT). 🟢 `rigctl.py:60-80`
- Cada comando abre uma conexão nova, recusa CR/LF e linhas acima de 160 caracteres, lê até 5 linhas e falha com `RigCtlError` em `RPRT -N` ou sem resposta. 🟢 `rigctl.py:28-58`
- Frequência válida nos dois sentidos: finita, de 1 kHz a 10 GHz. 🟢 `rigctl.py:66,77`
- Mapeamento de modos: SDR→Hamlib `NFM→FM`, `WFM`, `AM`, `USB`, `LSB`, `CW`, `DSB`; Hamlib→SDR `FM/FMN→NFM`, `CWR→CW`; modo desconhecido vira texto vazio na leitura e erro na escrita. 🟢 `rigctl.py:15-19`
- Ao ler, o SDR só sintoniza se a frequência estiver em 24 kHz–1766 MHz e for suportada pela fonte; senão mostra o motivo e não muda nada. O modo só muda se for reconhecido. 🟢 `ui/main_window.py:1523-1534`
- Uma operação por vez; os botões ficam desabilitados durante a comunicação. 🟢 `ui/rigctl_panel.py:77-92`
- Sincronização automática lê a cada 4 s (vigia de 300 ms) e só se a anterior terminou. Somente leitura: nunca envia ao rádio sozinha. 🟢 `ui/rigctl_panel.py:110-116`
- Configuração persistida: `cat_host`, `cat_port`, `cat_auto_sync` (padrão False). 🟢 `ui/rigctl_panel.py:71-75`
- Não expor a porta CAT à Internet; o programa não instala o Hamlib. 🟢 `ui/rigctl_panel.py:53-56`

## Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-01 | Ler rádio → SDR | Should | Frequência e modo aplicados ao SDR |
| RF-02 | Enviar SDR → rádio | Could | `F` e `M` enviados, mensagem confirma "PTT não foi acionado" |
| RF-03 | Seguir rádio a cada 4 s | Could | Leitura periódica com a caixa marcada |
| RF-04 | Nunca transmitir | Must | Nenhum comando de PTT no cliente |
| RF-05 | Validar entrada e resposta | Must | Frequência e comando fora do contrato são recusados |
| RF-06 | Não bloquear a UI | Must | Rede num `ThreadPoolExecutor` de 1 worker |

## Requisitos Não Funcionais

| Tipo | Requisito inferido | Evidência no código | Confiança |
|------|--------------------|---------------------|-----------|
| Segurança | Sem PTT, sem injeção de comando | `rigctl.py:28-30` | 🟢 |
| Responsividade | Timeout de 1,5 s por comando | `rigctl.py:21` | 🟢 |
| Segurança | Conexão em claro, sem autenticação (é o protocolo do rigctld) | `rigctl.py` | 🟡 |

## Critérios de Aceitação

```gherkin
Dado um rigctld que responde 145500000 e "FM"
Quando o operador clica "Ler rádio → SDR"
Então o SDR fica em 145,500 MHz NFM

Dado um rigctld que responde "RPRT -11"
Quando o operador lê o rádio
Então o status mostra "CAT: Hamlib: RPRT -11" e o SDR não muda

Dado o rádio em 3 GHz
Quando o operador lê o rádio
Então o status mostra "CAT: frequência fora da faixa do SDR Tool"

Dado o SDR em modo sem equivalente Hamlib
Quando o operador envia SDR → rádio
Então o status mostra "Modo … não suportado pelo rigctld"

Dado um rigctld fora do ar
Quando o operador lê o rádio
Então o status mostra o erro de conexão em até 1,5 s e os botões voltam a ficar ativos
```

## Prioridade (MoSCoW)

| Requisito | MoSCoW | Justificativa |
|-----------|--------|---------------|
| Nunca transmitir, validar | Must | Segurança e legalidade |
| Leitura | Should | Uso principal |
| Escrita e seguir automático | Could | Conveniência |

## Rastreabilidade de Código

| Arquivo | Função / Classe | Cobertura |
|---------|-----------------|-----------|
| `pt2vhf/rigctl.py` | `RigCtlClient`, `RigCtlError`, `SDR_TO_HAMLIB`, `HAMLIB_TO_SDR` | 🟢 |
| `pt2vhf/ui/rigctl_panel.py` | `RigCtlPanel` | 🟢 |
| `pt2vhf/ui/main_window.py` | `_cat_received`, aba "CAT · Hamlib" | 🟢 |
| `tests/test_v080_integrations.py` | servidor rigctld falso | 🟢 |
