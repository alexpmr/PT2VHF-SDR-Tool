# Atualização OTA

## Visão Geral
Verifica no site oficial `www.pt2vhf.com` se há versão nova, baixa o pacote do tipo de instalação (instalador ou portátil), confere tamanho e SHA-256 e entrega a instalação a um auxiliar PowerShell que fecha o programa, instala e o reabre. Execução pelo código-fonte só avisa. 🟢
🔴 O fluxo ponta a ponta no Windows real **não está homologado** (P0 do BACKLOG). Clientes v0.13.0 precisam de uma atualização manual única.

## Responsabilidades
- Detectar o tipo de instalação. 🟢
- Consultar e validar o manifesto. 🟢
- Baixar com verificação estrita e redirecionamento controlado. 🟢
- Instalar automaticamente quando o programa estiver livre, ou perguntar. 🟢
- Mostrar o resultado da atualização anterior. 🟢

## Regras de Negócio
- Tipo: `source` se não congelado; `portable` se existir `portable.flag` ao lado do EXE ou o nome terminar em `-portable`; senão `installer`. 🟢 `updater.py:64-72`
- Consulta: `GET https://www.pt2vhf.com/update.php?product=sdr&platform=windows-x64[&kind=…]`, `User-Agent: PT2VHF-SDR-Tool/<versão>`, sem redirecionamento, resposta até 2 MB. 🟢 `updater.py:161-179`
- Manifesto aceito: `schema` 1, `product` "sdr", `status` "available", versão `X.Y.Z` (com `v` opcional) mais nova que a instalada. 🟢 `updater.py:130-142`
- Pacote aceito: `kind` igual ao da instalação; URL oficial (`https`, host exato, nome `[A-Za-z0-9_.-]+.exe`, caminho `/downloads/sdr-tool/<nome>` ou `/download.php?product=sdr&file=<nome>`, sem credenciais, fragmento ou `%`); `size` inteiro em 1 B–600 MB; `sha256` com 64 hex minúsculos. 🟢 `updater.py:75-93,143-158`
- Versão nova sem pacote válido: botão "Versão X · OTA indisponível" com o motivo; **nunca abre o navegador como substituto** (desde v0.13.3). 🟢 `ui/assist_panels.py:266-280`
- Download: único redirecionamento permitido é site → `github.com/alexpmr/PT2VHF-SDR-Tool/releases/download/vX.Y.Z/<nome>` → CDN de assets do GitHub. `Content-Length` divergente, excesso de bytes, tamanho final ou SHA-256 diferente apagam o arquivo e abortam. 🟢 `updater.py:101-127,182-220`
- Verificação automática 12 s após abrir e a cada 6 h; manual pelo botão de versão ou menu. Código-fonte não verifica sozinho. 🟢 `ui/main_window.py:665-668`, `ui/assist_panels.py:224-226`
- Com `auto_update` (padrão True): instala sozinho se o programa estiver livre; ocupado (gravação, transmissão sendo gravada, scanner, varredura de memórias, replay, diálogo modal) adia e tenta a cada 60 s. 🟢 `ui/assist_panels.py:290-303`, `ui/main_window.py:1441-1457`
- Falha de download marca `update_failed` e não tenta a mesma versão automaticamente por 6 h. 🟢 `ui/assist_panels.py:200,294-296,366`
- Sem `auto_update`: pergunta "Atualizar agora / Depois"; "Depois" adia 24 h a mesma versão (`update_prompt_snooze`); espera diálogos modais (5 s). 🟢 `ui/assist_panels.py:305-330`
- Aplicar só em Windows congelado: copia `apply-update.ps1` para junto do pacote e o inicia destacado (`-WaitPid`, `-Mode Setup|Portable`); o programa fecha (saída forçada após 8 s). 🟢 `updater.py:236-255`, `ui/main_window.py:1459-1465`
- Auxiliar: Setup roda `/VERYSILENT … /LOG`; Portable faz backup `.previous`, até 10 tentativas de cópia e restaura em falha; nunca toca `%APPDATA%`; grava `ok|erro`, versão e detalhe em `%TEMP%\PT2VHF-SDR-Tool-update-result.txt` e reabre o programa. 🟢 `scripts/apply-update.ps1`
- Na abertura, o resultado é lido, apagado e mostrado. 🟢 `updater.py:258-270`, `ui/assist_panels.py:379-391`
- 🟡 A chave `check_updates` (DEFAULTS, padrão True) não é lida por ninguém; a que vale é `auto_update`, fora de DEFAULTS (dívida D8).

## Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-01 | Detectar tipo de instalação | Must | installer, portable, source |
| RF-02 | Validar manifesto e pacote | Must | Regras acima; motivo em texto |
| RF-03 | Download verificado | Must | Tamanho e SHA-256 conferem ou nada é instalado |
| RF-04 | Redirecionamento restrito | Must | Só a release da mesma versão |
| RF-05 | Instalação automática quando livre | Should | Adia se `operation_busy` |
| RF-06 | Pergunta com soneca de 24 h | Should | "Depois" adia a mesma versão |
| RF-07 | Resultado da atualização anterior | Should | Mensagem na abertura |
| RF-08 | Sem navegador como substituto | Must | Teste `test_ota_no_browser.py` |
| RF-09 | Funcionar no Windows real | Must | 🔴 Homologação pendente |

## Requisitos Não Funcionais

| Tipo | Requisito inferido | Evidência no código | Confiança |
|------|--------------------|---------------------|-----------|
| Segurança | Origem única HTTPS, sem redirecionamento livre | `updater.py:75-127` | 🟢 |
| Segurança | Integridade por SHA-256 publicado no próprio site (sem assinatura de código) | `updater.py:216-219` | 🟡 |
| Segurança | `-ExecutionPolicy Bypass` no auxiliar | `updater.py:231` | 🟢 |
| Disponibilidade | Programa atual nunca é alterado se a verificação falha | `updater.py:212-219` | 🟢 |
| Responsividade | Rede em threads; UI por sinais | `ui/assist_panels.py:228-234,344-350` | 🟢 |

## Critérios de Aceitação

```gherkin
Dado um instalador v0.13.3 e o site anunciando 0.13.4 com pacote installer válido
Quando a verificação automática roda com o programa livre
Então o pacote é baixado, conferido, o auxiliar é iniciado e o programa fecha

Dado o pacote baixado com SHA-256 diferente do manifesto
Quando o download termina
Então o arquivo é apagado, aparece "SHA-256 ou tamanho não confere" e nada é instalado

Dado o site redirecionando o download para outro host
Quando o download começa
Então aparece "Redirecionamento fora da release oficial PT2VHF."

Dado uma gravação em andamento
Quando há versão nova
Então o botão mostra "instala ao ficar livre" e a tentativa se repete a cada 60 s

Dado o manifesto com versão nova sem pacote portable
Quando a instalação portátil verifica
Então o botão mostra "OTA indisponível" e o navegador não abre

Dado execução pelo código-fonte
Quando o operador verifica manualmente
Então recebe "atualização manual" e nada é baixado
```

## Prioridade (MoSCoW)

| Requisito | MoSCoW | Justificativa |
|-----------|--------|---------------|
| Validação, integridade, redirecionamento | Must | Segurança da cadeia de atualização |
| Homologação no Windows | Must | P0 aberto |
| Automático e pergunta | Should | Experiência |

## Rastreabilidade de Código

| Arquivo | Função / Classe | Cobertura |
|---------|-----------------|-----------|
| `pt2vhf/updater.py` | `install_kind`, `is_official`, `select_update`, `check`, `download`, `apply`, `read_update_result`, `_PackageRedirect`, `_NoRedirect` | 🟢 |
| `pt2vhf/ui/assist_panels.py` | `UpdateController` | 🟢 |
| `pt2vhf/ui/main_window.py` | `operation_busy`, `quit_for_update`, agendamento | 🟢 |
| `pt2vhf/ui/settings_panel.py` | caixa `auto_update` | 🟢 |
| `scripts/apply-update.ps1` | auxiliar de instalação | 🟢 |
| `tests/test_ota_no_browser.py`, `tests/test_ota_site_release_redirect.py` | regressões | 🟢 |
