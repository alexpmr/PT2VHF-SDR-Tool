# Memórias e favoritos

## Visão Geral
Banco de canais do operador (memórias) com categorias, favoritos em barra de acesso rápido, pacotes de canais prontos, importação e exportação CHIRP, perfis por região e plano de bandas com pilha de frequências por banda. 🟢

## Responsabilidades
- Guardar, editar, remover e chamar canais com frequência, modo, largura, squelch e CTCSS. 🟢
- Organizar canais em categorias; categoria nova é criada ao adicionar. 🟢
- Mostrar favoritos como teclas de acesso rápido. 🟢
- Importar pacotes prontos sem duplicar. 🟢
- Importar e exportar CSV do CHIRP. 🟢
- Salvar e carregar bancos por região. 🟢
- Fornecer o plano de bandas e lembrar as últimas frequências por banda. 🟢

## Regras de Negócio
- `MemoryChannel`: `name`, `freq` (Hz), `mode` (NFM), `bandwidth` (12 000), `category` (Simplex), `squelch`, `ctcss`, `offset`, `notes`, `favorite`, `skip_scan`, `id` (uuid4 hex de 10). 🟢 `memory.py:61-80`
- Categorias padrão: Repetidoras, Simplex, APRS / Digital, Satélites, Aviação, Marítimo, Broadcast, Utilidades, Favoritos. 🟢 `memory.py:54-57`
- Sem arquivo de memórias, o banco nasce com `default_memories()`. 🟢 `memory.py:108-111`
- `memorias.json` = `{categories, channels}`; campos desconhecidos são ignorados no load. 🟢 `memory.py:114-119`
- `MemoryBank.save` não é atômico e o load não trata JSON corrompido (o programa falha ao abrir). 🟢 `memory.py:114-126`. 🟡 Risco de perda (dívida D4).
- Chamar uma memória aplica modo e largura, sintoniza e aplica o squelch salvo, se houver. 🟢 `ui/main_window.py:1210-1216`
- Salvar o canal atual propõe nome = frequência em MHz com 4 casas, categoria Favoritos e o CTCSS medido. 🟢 `ui/main_window.py:1218-1222`
- Barra de favoritos: favoritos ordenados por categoria e frequência; tecla marcada se o VFO está a menos de 1 Hz (60 Hz ao remarcar); menu "Remover dos favoritos"; sem favoritos, mostra uma dica. 🟢 `ui/listening.py:57-95`
- Pacotes: Radioamador chamada e fonia, modos digitais (FT8/FT4/WSPR), Satélites e ISS, Aviação, Marítimo VHF, PX 11 m, Rádio comunicador (FRS/PMR446), Sinais horários (HF). Não duplica pela chave (categoria, freq/100). 🟢 `presets.py:130-168`
- CHIRP: Frequency em MHz; FM→NFM 12 kHz, NFM 8 kHz, WFM 180 kHz, AM 8 kHz, USB/LSB 2,7 kHz, CW 500 Hz, outros→NFM; CTCSS de `rToneFreq`/`cToneFreq` quando Tone/TSQL; nome exportado até 16 caracteres; Skip = S vira `skip_scan`; coluna extra Category. 🟢 `memory.py:166-230`
- Regiões: nome de 1 a 100 caracteres sem caracteres de controle; gravação atômica; carregar uma região substitui o banco ativo e grava. Importar CHIRP sem canais válidos dá erro. 🟢 `memory_regions.py:11-70`
- Plano de bandas com 21 faixas (160 m a 23 cm, mais FM, aviação, satélites meteo, marítimo, PMR), cada uma com modo e passo. 🟢 `memory.py:22-44`
- Pilha por banda: guarda até 3 entradas (frequência, modo) por banda, sem repetir frequências a menos de max(1 kHz, 2 × passo) no mesmo modo; clicar de novo na banda atual alterna a entrada; sem histórico, vai ao meio da banda no modo padrão. 🟢 `ui/main_window.py:985-1015`
- Banda não suportada pelo SDR: mensagem por 12 s e nada é sintonizado. 🟢 `ui/main_window.py:996-999`
- Pedidos do backlog, **não implementados**: favoritos em menu suspenso para economizar espaço e favoritos ordenados por frequência de uso. 🔴 memória do projeto

## Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-01 | CRUD de memórias com categorias | Must | Canal salvo reaparece após reiniciar |
| RF-02 | Chamar memória | Must | Modo, largura, frequência e squelch aplicados |
| RF-03 | Barra de favoritos | Must | Clique chama; menu remove |
| RF-04 | Pacotes prontos sem duplicar | Should | Importar duas vezes não cria cópias |
| RF-05 | Importar e exportar CHIRP | Should | Ida e volta preserva frequência, modo e tom |
| RF-06 | Perfis por região | Should | Carregar troca o banco ativo |
| RF-07 | Plano de bandas e pilha por banda | Must | Ver regras |
| RF-08 | Marcar `skip_scan` | Should | Canal fora da varredura |
| RF-09 | Favoritos em menu suspenso e por uso | Could | Backlog 🔴 |

## Requisitos Não Funcionais

| Tipo | Requisito inferido | Evidência no código | Confiança |
|------|--------------------|---------------------|-----------|
| Integridade | Regiões gravadas de forma atômica | `memory_regions.py:30-35` | 🟢 |
| Integridade | Memórias e config sem gravação atômica | `memory.py:121-126` | 🟢 |
| Compatibilidade | CSV com BOM (`utf-8-sig`) aceito | `memory.py:171` | 🟢 |

## Critérios de Aceitação

```gherkin
Dado um banco sem o pacote Marítimo
Quando o operador importa o pacote duas vezes
Então os canais aparecem uma vez só

Dado um CSV do CHIRP com uma linha FM 145.500 Tone 88.5
Quando o operador importa
Então surge um canal NFM de 12 kHz em 145,500 MHz com CTCSS 88,5 Hz

Dado o nome de região vazio
Quando o operador salva a região
Então aparece o erro "Nome de região inválido (1–100 caracteres)"

Dado o VFO em 145,500 MHz NFM na banda 2 m
Quando o operador vai para 70 cm e volta para 2 m
Então o VFO volta para 145,500 MHz NFM

Dado um RTL-SDR sem HF
Quando o operador clica na banda 40 m
Então aparece o motivo na barra de status e nada é sintonizado
```

## Prioridade (MoSCoW)

| Requisito | MoSCoW | Justificativa |
|-----------|--------|---------------|
| Banco de memórias, chamada, favoritos | Must | Uso diário |
| Plano de bandas e pilha | Must | Teclas de banda dependem dele |
| CHIRP, pacotes, regiões | Should | Importação e organização |
| Menu suspenso e ordem por uso | Could | Backlog |

## Rastreabilidade de Código

| Arquivo | Função / Classe | Cobertura |
|---------|-----------------|-----------|
| `pt2vhf/memory.py` | `Band`, `BAND_PLAN`, `band_for`, `MemoryChannel`, `MemoryBank`, `default_memories`, `DEFAULT_CATEGORIES` | 🟢 |
| `pt2vhf/presets.py` | `PresetPack`, `PACKS`, `import_packs` | 🟢 |
| `pt2vhf/memory_regions.py` | `RegionMemoryStore` | 🟢 |
| `pt2vhf/ui/listening.py` | `FavoritesBar`, `PresetDialog` | 🟢 |
| `pt2vhf/ui/panels.py` | `MemoryDialog` (`panels.py:571`), `MemoryPanel` (`panels.py:636`) [Revisão: 🟡→🟢] | 🟢 |
| `pt2vhf/ui/main_window.py` | `_recall`, `_save_current_memory`, `_remember_current_band`, `_goto_band`, `_unfavorite` | 🟢 |
