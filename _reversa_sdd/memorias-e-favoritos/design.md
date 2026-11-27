# Memórias e favoritos, Design Técnico

## Interface

| Símbolo | Assinatura | Retorno | Observação |
|---------|-----------|---------|------------|
| `MemoryBank.__init__` | `(path: Path \| None = None)` | — | Carrega ou usa os padrões |
| `load` / `save` | `()` | — | JSON `{categories, channels}` |
| `add` | `(ch)` | — | Cria a categoria se faltar |
| `remove` / `get` | `(ch_id)` | — / `MemoryChannel \| None` | |
| `by_category` / `in_range` | `(cat)` / `(f0, f1)` | `list[MemoryChannel]` | |
| `export_csv` | `(path, channels=None)` | — | `CHIRP_FIELDS` + Category |
| `import_csv` | `(path, category=None)` | `int` | Nº de canais |
| `import_packs` | `(bank, keys, favorite=False)` | `int` | Canais novos |
| `RegionMemoryStore` | `(path)` | — | `names`, `save_bank`, `import_chirp`, `load_bank` |
| `band_for` | `(freq)` | `Band \| None` | |
| `MemoryChannel.band` | propriedade | `str` | Nome ou "Fora de banda" |
| `FavoritesBar` sinais | `recallRequested(object)`, `addCurrentRequested()`, `unfavoriteRequested(object)` | — | |
| `FavoritesBar.refresh` / `mark_current` | `(channels, current_freq)` / `(freq)` | — | |

## Fluxo Principal
1. Na abertura, `MemoryBank(config_dir/"memorias.json")`. 🟢
2. O painel de memórias e a barra de favoritos leem `bank.channels`. 🟢
3. Clique num favorito → `recallRequested` → `_recall(ch)`. 🟢
4. Edições chamam `bank.save()`; ao fechar, `cfg.save()`, `bank.save()` e `occupancy.flush(force=True)`. 🟢 `ui/main_window.py:2356-2358`
5. Teclas de banda → `_goto_band` → pilha da banda → sintonia. 🟢

## Fluxos Alternativos
- **Linha CHIRP sem frequência válida:** ignorada. 🟢
- **`load_bank` de região inexistente:** `KeyError`. 🟢
- **JSON de memórias corrompido:** exceção na abertura. 🔴 sem tratamento.

## Dependências
- `csv`, `json`, `uuid`. 🟢
- Config `band_stacks`. 🟢
- Scanner (varredura de memórias), waterfall (marcadores). 🟢

## Decisões de Design Identificadas

| Decisão | Evidência no código | Confiança |
|---------|---------------------|-----------|
| CHIRP como formato de troca | `memory.py:66-230` | 🟢 |
| Regiões separadas para não misturar cidades (v0.8.0) | `memory_regions.py:12`, CHANGELOG | 🟢 |
| Deduplicação de pacotes por categoria e freq/100 | `presets.py:153-161` | 🟢 |

## Estado Interno
`MemoryBank.channels`, `MemoryBank.categories`, `RegionMemoryStore.profiles`, `cfg["band_stacks"]`, `MainWindow.current_mem`. 🟢

## Observabilidade
Sem logs específicos. 🟢

## Riscos e Lacunas
- 🔴 JSON de memórias corrompido impede a abertura.
- 🟡 `save` não atômico.
- 🔴 Backlog: favoritos em menu suspenso e por frequência de uso.
