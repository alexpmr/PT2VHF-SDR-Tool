# PT2VHF SDR Tool v1.0.0 — plano de release (12/11/2026)

**A próxima release pública será v1.0.0**, exibida como v1.0. A branch de implementação prepara a versão, mas não está publicada.

## Splash (mesmo padrão SAT Tool v1.7.2)

- Referência consultada: alexpmr/PT2VHF-Sat-Tool, tag v1.7.2, sat_tool/app.py, função show_official_site_notice e tests/test_v172_welcome_banner.py.
- O código em pt2vhf/ui/welcome.py oferece banner inteiro e proporcional, clique para www.pt2vhf.com, link, botão Fechar, contador ⏱ 10 s e barra laranja que encolhe.
- Mantido o timer de 1800 ms de MainWindow._startup_notices e a regra PT2VHF_NO_STARTUP_DIALOGS; o aviso sobre a última atualização permanece posterior ao splash.
- O banner fornecido pelo usuário inclui sete projetos: APRS Client PC/Android, SAT Tool, QSL Manager, SDR Tool, Mesh Analyzer, Prop Tool e Prog Tool. Conversão offline sem corte pelo scripts/prepare_splash.py, destino pt2vhf/assets/branding/welcome-banner.jpg (1200 × 675).
- pt2vhf.spec inclui o JPEG tanto em Windows Setup (onedir) quanto Portable (onefile), falhando se o arquivo estiver ausente. pyproject.toml registra package-data para ambientes Python, Linux e macOS. Não alegar que já existem builds oficiais Linux/macOS se não houver workflow.
- Testes Qt cobrem clique, proporção, fechamento imediato, timer, progressão e permanência da regra de inicialização.

## Portão P0 de publicação

- Após v0.13.3 o usuário reportou encerramento inesperado; issue #8 e PR #9, correção ainda não homologada. O catálogo OTA público recomenda provisoriamente v0.13.2.
- Não publicar v1.0.0, nem atualizar site ou OTA, até: (1) incorporar o arquivo binário JPEG real ao GitHub, (2) CI Linux/Windows, Setup/Portátil e asset em ambos, (3) resolver a falha Windows e realizar teste prolongado com SDR real, (4) verificar OTA ponta a ponta entre versões.
- IA IQ/ONNX PR #2 segue experimental, sem merge. Não há liberação automática de v1.0.0.

**Estado:** código, tests, asset-builder e versionamento preparados em branch; inclusão do JPEG no GitHub e homologação ainda pendentes.
