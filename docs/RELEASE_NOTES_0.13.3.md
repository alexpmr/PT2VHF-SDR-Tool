# PT2VHF SDR Tool 0.13.3 — candidata de manutenção OTA

**Status:** candidata de teste; não publicada. **Não confundir** com a v0.13.2, já aprovada e lançada no GitHub.

## Correções e segurança

- Evita abrir o navegador como substituto silencioso do download OTA quando a atualização é detectada, mas nenhum pacote compatível foi selecionado.
- Informa por que o pacote foi rejeitado: URL não aceita, SHA-256/tamanho ausentes ou inválidos, ou pacote do tipo de instalação indisponível.
- Mantém `update.php` do site, validação de URL do `download.php`, redirecionamento restrito à release e verificação de tamanho/SHA-256 **antes de substituir qualquer executável**.
- Mantém a atualização automática (quando há arquivo válido e aplicativo livre) e o modo de confirmação manual já existentes.
- Acrescenta testes de regressão Qt para garantir que nenhum navegador seja aberto se o manifesto não contém pacote válido.

## Incidente de migração da v0.13.0

A v0.13.0 aceitava apenas URLs de download diretas `/downloads/sdr-tool/<arquivo>`. O endpoint oficial passou a fornecer `/download.php?product=sdr&file=<arquivo>`, levando `UpdateInfo.file=None` e ao encaminhamento para o site, sem download nem instalação. O cliente v0.13.1 já reconhece com segurança esse contrato.

**A v0.13.0 compilada não pode receber retroativamente a correção de URL.** Quem ainda usa v0.13.0 precisa fazer **uma atualização manual única para v0.13.1 ou superior**, preservando sua modalidade (Instalador ou Portátil). O OTA interno deve ser validado nas atualizações seguintes.

## Critérios de QA antes de publicar

1. Linux/Qt e Windows/Qt aprovados no SHA final do PR #5.
2. Windows x64: EXE portátil, Setup, teste de instalação silenciosa, inicialização, backup/rollback e OTA helper aprovados.
3. `update.php` ao vivo: tipos `installer` e `portable`, URLs aceitas, campos de tamanho e SHA-256 válidos.
4. Atualização ponta a ponta de uma v0.13.1 instalada para a próxima versão, com download verificado, instalação, reinício e mensagem de novidades.
5. Verificar GitHub release, SHA-256 e `www.pt2vhf.com/updates.json` e downloads após o deploy.

A IA experimental de classificação IQ/ONNX permanece isolada no PR #2; não incluir modelos não homologados com RF real.
