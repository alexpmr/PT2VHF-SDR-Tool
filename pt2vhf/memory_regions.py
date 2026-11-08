"""Perfis locais de memórias por região, compatíveis com CSV CHIRP."""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .memory import DEFAULT_CATEGORIES, MemoryBank, MemoryChannel


class RegionMemoryStore:
    """Salva bancos por região sem misturar canais de cidades distintas."""
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.profiles: dict[str, dict] = {}
        if self.path.exists():
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                self.profiles = data.get("regions", {})

    def names(self) -> list[str]:
        return sorted(self.profiles, key=str.casefold)

    @staticmethod
    def _check(name: str) -> str:
        name = name.strip()
        if not name or len(name) > 100 or any(ord(c) < 32 for c in name):
            raise ValueError("Nome de região inválido (1–100 caracteres)")
        return name

    def _persist(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"regions": self.profiles}, indent=2, ensure_ascii=False),
                       encoding="utf-8")
        tmp.replace(self.path)

    def save_bank(self, name: str, bank: MemoryBank):
        name = self._check(name)
        self.profiles[name] = {
            "categories": list(bank.categories),
            "channels": [asdict(c) for c in bank.channels],
        }
        self._persist()

    def import_chirp(self, name: str, csv_path: str | Path) -> int:
        name = self._check(name)
        tmp = MemoryBank(None)
        tmp.channels = []
        tmp.categories = list(DEFAULT_CATEGORIES)
        count = tmp.import_csv(str(csv_path))
        if not count:
            raise ValueError("CSV CHIRP sem canais válidos")
        self.save_bank(name, tmp)
        return count

    def load_bank(self, name: str, bank: MemoryBank) -> int:
        name = self._check(name)
        if name not in self.profiles:
            raise KeyError(name)
        data = self.profiles[name]
        fields = MemoryChannel.__dataclass_fields__
        channels = [MemoryChannel(**{k: v for k, v in ch.items() if k in fields})
                    for ch in data["channels"]]
        # Prepara tudo antes de modificar o banco ativo.
        categories = list(data.get("categories", DEFAULT_CATEGORIES))
        bank.channels = channels
        bank.categories = categories
        bank.save()
        return len(channels)
