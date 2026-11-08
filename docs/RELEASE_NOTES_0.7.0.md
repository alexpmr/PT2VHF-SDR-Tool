# PT2VHF SDR Tool v0.7.0 — Notas de versão

## Funcionalidades entregues no código
- Instrumentos analógicos S-meter e VU vetoriais, com três estilos, selecionáveis em Configurações → Display.
- Mapa de calor persistente por detecção do scanner (frequência/hora, janela móvel de 24 h), com exportação CSV.
- Perfil "Sinal fraco · DSP" (NB, NR e AGC) e restauração dos ajustes anteriores. Sem modelo neural.
- Legendas de fonia em blocos de poucos segundos com histórico, hora, frequência, modo, idioma e indicativos e exportação CSV.

## Limitações
- Legendas dependem de faster-whisper e modelo disponível localmente. Não há tradução automática nem backend embarcado.
- A versão não implementa decodificadores ADS-B/AIS/DMR/D-STAR/C4FM/SSTV/RS41 e não se declara completa.
- A atividade de 24 h é quantidade de detecções, não ocupação RF contínua.
- Testes físicos RTL-SDR devem ser realizados antes de declarar suporte definitivo.

## Entrega e publicação
Os binários Windows Setup/Portable precisam passar pelo pipeline GitHub Actions, autoteste, instalação silenciosa e SHA-256.
O endereço público de download e atualização é https://www.pt2vhf.com/sdr.
A atualização do manifesto do site deve ocorrer apenas com os pacotes gerados e conferidos.
