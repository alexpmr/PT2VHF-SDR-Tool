# PT2VHF SDR Tool v0.13.0 — Notas de versão

## Mudanças implementadas
- LCD redimensionável manualmente entre 50% e 150% em **Configurações → Display**, preservando proporção de todos os elementos; preferência salva e restaurada na próxima execução.
- Matriz de bandas compactada em até cinco colunas: **oculta** as bandas incompatíveis com o SDR ativo, atualiza ao trocar de dispositivo/fonte e mantém preferências ocultas para outros receptores.
- Verificação de sintonia conforme o tuner RTL-SDR, o protocolo rtl_tcp, as faixas reportadas pelo SoapySDR e a largura fixa de uma gravação IQ. No modo simulador, permite testes sem hardware.
- Navegação reunida em **Decodificação** (ADS-B, Sondas Meteorológicas, AIS, APRS/DTMF/CTCSS) e **Ferramentas** (Transcrição e Legendas ao vivo). A aba Satélites foi removida da barra principal, preservando a biblioteca orbital.
- Legendas em popup na tela do receptor: somente texto reconhecido, sem metadados. As configurações Whisper e o histórico permanecem em Ferramentas.

## Testes e limites
- Suíte automatizada Linux/Qt (offscreen) passou antes do incremento de versão, incluindo testes de escala, persistência, navegação e bandas ocultas. O workflow Windows é o critério para produzir instaladores oficiais.
- O reconhecimento local Whisper depende de download explícito de pesos e pode sofrer atrasos de alguns segundos. A qualidade deve ser conferida com transmissões reais.
- A demodulação RS41 ainda depende de **fsk_demod/rs41mod** e não foi homologada com SDR real; sinais no waterfall não provam quadros válidos.
- ADS-B/AIS ainda dependem de fontes externas; SSTV, DMR/D-STAR/C4FM, tradução offline, IA de IQ e outros decodificadores permanecem pendentes.
- Não declarar publicação ou atualização OTA até validar Setup/Portable no Windows, SHA-256, página de downloads e manifesto do site oficial.
