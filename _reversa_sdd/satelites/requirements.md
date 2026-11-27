# Satélites

## Visão Geral
Calcula a posição (azimute, elevação, distância) e o Doppler de recepção de satélites a partir de arquivos TLE do operador, prevê passagens nas próximas 24 h e pode seguir o Doppler retunando o VFO. Somente recepção. 🟢

## Responsabilidades
- Ler TLEs (2 ou 3 linhas) de um arquivo local. 🟢
- Propagar com SGP4 e converter para azimute/elevação do observador. 🟢
- Calcular o desvio Doppler de recepção. 🟢
- Prever passagens por amostragem. 🟢
- Sintonizar a frequência corrigida, uma vez ou continuamente. 🟢

## Regras de Negócio
- TLE: ignora linhas vazias e comentários `#`; nome opcional (prefixo `0 ` removido); linhas 1 e 2 com ≥ 68 caracteres e o mesmo número NORAD; sem nome, usa o NORAD. 🟢 `satellites.py:39-56`
- Conversão TEME → ECEF por rotação sideral (GMST), sem nutação nem movimento polar: adequado para rastreio amador aproximado, não para determinação de órbita. 🟢 `satellites.py:1-5,94-99`
- Observador no elipsoide WGS-84; posição a partir do locator Maidenhead (`my_locator`); locator inválido mostra "Informe um locator Maidenhead válido (ex.: GH64cd)". 🟢 `satellites.py:65-74`, `ui/satellite_panel.py:143-147`
- Data deve ter fuso (UTC); lat/lon fora dos limites levanta `ValueError`; erro do SGP4 vira `ValueError`. 🟢 `satellites.py:79-90`
- Doppler RX = −f·v_radial/c (não relativístico); afastando = negativo; frequência nominal válida de 1 kHz a 10 GHz. 🟢 `satellites.py:114-118`
- Passagens: passo mínimo 5 s (padrão 45 s), até 20 000 amostras, elevação mínima 0°; cada passagem tem AOS, pico, LOS e elevação máxima. 🟢 `satellites.py:121-141`
- Seguir Doppler só retuna com o satélite acima do horizonte. 🟢 `ui/satellite_panel.py:164`
- Frequência nominal na UI entre 0,001 e 1766 MHz; padrão 145,800 MHz. 🟢 `ui/satellite_panel.py:50-53`
- Config: `sat_tle_path`, `sat_nominal_hz`, `sat_doppler_auto`. 🟢
- O `SatellitePanel` é criado e ligado à sintonia, mas não está em nenhuma aba desde a remoção da aba Satélites (biblioteca orbital preservada). 🟢 `ui/main_window.py:272,618`, CLAUDE.md
- Sem `sgp4` instalado: "Dependência sgp4 não instalada". 🟢 `satellites.py:23-27`

## Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-01 | Carregar TLEs | Should | Lista de satélites com nomes |
| RF-02 | Mostrar az, el, distância e Doppler | Should | Resumo atualizado pelo timer |
| RF-03 | Passagens das próximas 24 h | Should | Tabela AOS/pico/LOS/el máx |
| RF-04 | Sintonizar com Doppler | Should | Botão sintoniza a frequência corrigida |
| RF-05 | Seguir Doppler | Could | Retuna só acima do horizonte |
| RF-06 | Painel acessível na UI | Could | 🔴 hoje fora das abas |

## Requisitos Não Funcionais

| Tipo | Requisito inferido | Evidência no código | Confiança |
|------|--------------------|---------------------|-----------|
| Precisão | Aproximada, sem nutação/movimento polar | `satellites.py:1-5` | 🟢 |
| Limite | Até 20 000 amostras por previsão | `satellites.py:125` | 🟢 |
| Privacidade | TLE só de arquivo local, sem download | `satellites.py:1` | 🟢 |

## Critérios de Aceitação

```gherkin
Dado um arquivo TLE com a ISS e o locator GH64cd
Quando o operador calcula passagens
Então a tabela mostra as passagens das próximas 24 h com elevação máxima

Dado um satélite se aproximando a 7 km/s em 145,800 MHz
Quando o Doppler é calculado
Então o desvio é de cerca de +3,4 kHz

Dado um locator vazio
Quando o painel atualiza
Então aparece "Satélite: Informe um locator Maidenhead válido (ex.: GH64cd)"

Dado o seguimento ligado e o satélite abaixo do horizonte
Quando o timer atualiza
Então o VFO não muda
```

## Prioridade (MoSCoW)

| Requisito | MoSCoW | Justificativa |
|-----------|--------|---------------|
| Biblioteca orbital (TLE, SGP4, Doppler, passagens) | Should | Preservada de propósito |
| Painel na UI | Could | Removido das abas |

## Rastreabilidade de Código

| Arquivo | Função / Classe | Cobertura |
|---------|-----------------|-----------|
| `pt2vhf/satellites.py` | `TLESatellite`, `LookAngle`, `parse_tles`, `look_angle`, `receive_doppler_hz`, `next_passes` | 🟢 |
| `pt2vhf/ui/satellite_panel.py` | `SatellitePanel` | 🟢 |
| `pt2vhf/decoders/aprs.py` | `locator_to_latlon` | 🟢 |
