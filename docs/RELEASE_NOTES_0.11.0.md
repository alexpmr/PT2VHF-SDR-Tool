# PT2VHF SDR Tool v0.11.0 — Notas de versão

## Mudanças
1. S-meter: leitura inicial em branco, sem sete barras fixas; atualização proporcional do nível conforme amostras IQ recentes. Tooltip com dBFS/dBm e texto S; escala ainda depende de calibração do SDR.
2. LCD: desenho vetorial em escala uniforme e coordenadas de clique ajustadas; a grade de seleção das bandas ocupa o espaço à direita da frequência em matriz de cinco colunas, acima do S-meter. Bandas indisponíveis ficam esmaecidas, como nas versões anteriores.
3. Radiossondas RS41: o sinal IQ deixa de ser deslocado para +12 kHz, pois a máscara -5/+5 kHz do fsk_demod moderno exige portadora centrada em 0 Hz. Corrigida a chamada do demodulador.
4. Mantidos recursos de v0.10.0: abas ADS-B/AIS/Sondas independentes, rastros OSM/GPX/KML, CAT, TLE/Doppler, memórias por região.

## Critérios de homologação
- Testes automatizados Linux/Windows, autotestes PyInstaller e instalação silenciosa Inno Setup.
- Teste visual LCD em 1.100, 800, 550 e 360 pixels de largura, clicando nos modos e nas bandas.
- Teste S-meter com SDR real: sem RF, sinal fraco/forte, ajuste de ganho e retune; verificar coerência da leitura.
- RS41: teste com IQ real capturado e binários fsk_demod/rs41mod compatíveis, prova de serial/posição/altitude decodificados e checagem de perdas.

## Limitações
- Testes com simulador e gravação de tom IQ não comprovam recepção de radiossonda RS41 real.
- Faltam fsk_demod e rs41mod incluídos nos instaladores; o operador deve fornecer executáveis válidos e verificáveis.
- Demodulação de outros modelos de sonda, SSTV, voz digital, IA neural, ACARS, WFM RDS, KiwiSDR e tradução integral permanecem no backlog.
- A publicação/OTA no site www.pt2vhf.com depende de efetiva implantação na hospedagem, não apenas do commit do repositório.

Referência técnica: https://github.com/projecthorus/radiosonde_auto_rx/blob/master/auto_rx/autorx/decode.py

## Construção Windows
- Pipeline requerido para distribuir Setup e Portable, com testes locais de executáveis e Inno Setup.
- Verificar SHA256SUMS e tag v0.11.0 antes de promover ao site.
