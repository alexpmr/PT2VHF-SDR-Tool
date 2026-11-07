# Backlog — PT2VHF SDR Tool

Itens registrados pelo mantenedor. Não implementar até o pedido de versão nova.

## Pendentes

### IA para fonia SSB (registrado em 07/11/2026)
- **Sintonia fina automática de SSB:** estimar o deslocamento da portadora pelos harmônicos da voz
  e corrigir o VFO sozinho (sem processar o áudio).
- **Detecção automática de modo e banda lateral** (USB/LSB/AM/FM/CW/digital) ao clicar num sinal,
  ajustando modo e filtro.
- **Filtro adaptativo:** bordas do passband ajustadas ao sinal e à interferência adjacente.
- **Transcrição local da fonia (opcional, ex.: Whisper):** log pesquisável e destaque de indicativos.

### Escuta avançada (registrado em 07/11/2026)
- **Voltar no tempo:** buffer dos últimos 30–60 s de IQ para reouvir (inclusive outra frequência da faixa).
- **Vários receptores simultâneos** dentro da mesma faixa (ex.: torre e solo do aeroporto).

### Publicação
- **Instalador para Windows:** só gerar quando o mantenedor pedir. Na publicação, incluir `sdr` em
  `download.php`, `update.php` e `.htaccess` do site e adicionar a verificação de atualização pelo
  `update.php?product=sdr`.

## Concluídos
- 0.2.0 — memórias prontas, favoritos, scanner por espectro e gravação por atividade.
- 0.1.0 — primeira versão.
