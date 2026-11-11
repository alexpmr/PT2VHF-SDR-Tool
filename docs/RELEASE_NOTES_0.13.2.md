# PT2VHF SDR Tool v0.13.2 — candidata de manutenção

**Status:** proposta em revisão; **não publicada** até aprovação integral dos testes Linux e Windows, geração dos instaladores e validação da distribuição oficial.

## Correções implementadas nesta candidata

- **Waterfall — sintonia por clique com zoom e pan:** mantém o mapeamento do ponto da tela para a frequência RF e o ajuste ao passo de canal, mas agora só aceita cliques dentro do espectro IQ de fato adquirido. Regiões visualmente vazias fora da largura recebida não alteram o VFO.
- **Waterfall — arraste do passband:** rejeita tentativas de arrastar a sintonia além da largura IQ disponível e restaura o indicador do VFO quando um arraste seria inválido.
- **Waterfall — duplo clique:** o reset do zoom só é executado quando o clique estiver sobre uma área de espectro ou waterfall.
- **Testes de regressão:** novo conjunto Qt offscreen de conversão cena→frequência, passband, limites de Nyquist, arredondamento por passo e ausência de IQ.
- **Mantém as correções da v0.13.1:** contrato OTA do site, integridade SHA-256 e testes de instalação/recuperação existentes.

## Limites e pré-requisitos de publicação

- Esses testes são automatizados e sintéticos, não representam ensaio RF em bancada. Confirmar sintonia e recepção em dispositivo SDR real continua recomendado.
- A IA experimental IQ/ONNX permanece **fora da release**. Seu PR #2 não deve ser mesclado sem validação independente com RF real, OOD, desempenho e reprodutibilidade.
- RS41 real, calibração absoluta do S-meter e reconhecimento de sinais neurais continuam sem homologação.
- Somente **Windows x64 Setup e Portable** são gerados pelo workflow atual; não anunciar executáveis macOS/Linux inexistentes.
- Verificar testes Linux/Qt, Windows/Qt, helper OTA, build PyInstaller, instalador Inno Setup e autoteste após instalação, além dos hashes.
- A v0.13.1 existe no GitHub, mas havia divergência entre o site oficial em produção e o repositório PT2VHF-Site (issue [#18](https://github.com/alexpmr/PT2VHF-Site/issues/18)). **Não declarar esta versão publicada no site sem conferência real de updates.json, update.php e downloads**.

## Origem

- Branch de desenvolvimento: `release/stable-v0.13.2` derivada da `main` na v0.13.1.
- Site alvo: https://www.pt2vhf.com/sdr
