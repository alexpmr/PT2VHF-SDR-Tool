# Controle de build: PT2VHF SDR Tool v0.7.0

Esta versão é distribuída somente após:
1. suíte de testes automatizados sem falhas, incluindo encerramento Qt;
2. build Windows 64 bits no GitHub Actions;
3. autoteste do Setup e do Portable;
4. instalação silenciosa de teste no runner Windows;
5. geração de SHA256SUMS.txt;
6. publicação da release no repositório SDR Tool.

A release do GitHub é fonte dos instaladores, e não implica publicação
automática no site PT2VHF. Manter o OTA em 0.6.0 ou na última versão
efetivamente entregue pelo site até os novos pacotes serem verificados.

## Correções de estabilidade
- Servidor HTTP local/LAN finaliza as threads antes do encerramento (sem shutdown em daemon).
- Recuperação automática do RTL-SDR reutiliza a única thread de controle, sem duplicatas após reconexão.
- Testes adicionais de fechamento de thread HTTP e thread USB, e escape HTML de pacotes APRS não confiáveis.
- PySide6 6.11.3 fixado nas dependências Windows/Linux para reprodutibilidade.
