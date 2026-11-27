# Radiossonda RS41, Perguntas em aberto

Lacunas 🔴 que dependem de validação humana ou de RF real.

1. **Existe alguma captura IQ real de RS41 com quadros conhecidos?** Sem ela não há teste de regressão do pipeline completo.
2. **Qual versão do `fsk_demod`/`rs41mod` é a de referência?** Os argumentos assumem a máscara ±5 kHz do `fsk_demod` atual (commit fa10118).
3. **O ganho e o PPM do RTL-SDR em 400–406 MHz foram conferidos?** Um desvio de frequência maior que a máscara impede o travamento.
4. **A estação do operador alcança sondas em voo?** Define se a homologação pode ser feita em casa ou exige deslocamento.
5. **A memória do projeto cita RS41 embarcado na v1.0.7.** Essa implementação substitui a desta branch? Se sim, esta spec descreve o legado v0.13.x.
