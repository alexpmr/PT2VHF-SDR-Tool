# PT2VHF SDR Tool v0.13.1 — release candidate de manutenção

**Situação:** candidata em validação. Não anunciar como publicada até concluir build Windows, OTA ponta a ponta e verificações do site.

## Escopo

- Preserva as funcionalidades estáveis existentes na v0.13.0, sem mesclar o PR neural experimental #2.
- Corrige a compatibilidade do cliente OTA com o formato real do manifesto de `https://www.pt2vhf.com/update.php`, que fornece download via `download.php?product=sdr&file=...`.
- Restringe os redirecionamentos a site oficial → release GitHub com versão e nome de arquivo esperados → CDN de artefatos GitHub; rejeita destinos arbitrários.
- Mantém verificação de tamanho e SHA-256 do pacote antes de permitir a aplicação da atualização.
- Acrescenta testes de contrato e rejeição de redirecionamentos indevidos.

## Critérios de publicação (obrigatórios)

1. CI Linux/Qt e testes de regressão OTA aprovados no SHA da candidata.
2. Job Windows x64, normalmente ignorado por padrão, **efetivamente executado e aprovado**: testes, PyInstaller (Setup/Portable), self-tests, Inno Setup e instalação silenciosa.
3. Verificar cadeia de redirecionamentos do site e concluir instalação OTA ponta a ponta nos formatos Setup e Portable, incluindo hashes e tratamento de falhas/rollback. A implementação de detecção e download **não prova** instalação automática real.
4. Conferir compatibilidade da versão nos metadados Python/EXE, release, site `/sdr`, `updates.json` e `update.php`.
5. Validar publicamente os links de download e SHA-256 antes de comunicar disponibilidade.

## Exclusões e limites

- **Não incluir nem habilitar o classificador neural IQ/ONNX**. Os modelos v2–v5 permanecem na branch `feature/iq-signal-classifier`, PR #2, com divergência entre arquiteturas de CPU e sem validação de RF real.
- Transcrição com Whisper/RNNoise mantida como já disponível no ramo estável; não afirmar reconhecimento de modulação neural homologado.
- Não afirmar validação operacional de RS41, S-meter absoluto, waterfall, taxa de quadros ou performance RF apenas com testes sintéticos.
- O pipeline existente gera **Windows x64 Setup e Portable**. Não anunciar instaladores Linux/macOS inexistentes nesse workflow.

## Origem

- Branch candidata: `release/stable-v0.13.1` baseada na `main` v0.13.0.
- Publicação oficial: https://www.pt2vhf.com/sdr (somente após conclusão e verificação).
