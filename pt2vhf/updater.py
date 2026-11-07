"""Atualização automática pelo site oficial (somente www.pt2vhf.com).

1. Consulta https://www.pt2vhf.com/update.php?product=sdr&platform=windows-x64&kind=<installer|portable>
2. Se houver versão maior, baixa o arquivo do próprio site, conferindo tamanho e SHA-256.
3. Instalador: executa o setup e fecha o programa. Portátil: substitui o .exe e reabre.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from . import __version__

OFFICIAL_HOST = "www.pt2vhf.com"
UPDATE_URL = f"https://{OFFICIAL_HOST}/update.php"
PRODUCT = "sdr"
USER_AGENT = f"PT2VHF-SDR-Tool/{__version__}"


class UpdateError(Exception):
    pass


@dataclass
class UpdateInfo:
    version: str
    date: str
    notes: str
    page: str
    file: dict | None


def parse_version(v: str) -> tuple[int, ...]:
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)", v or "")
    return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)


def is_newer(remote: str, local: str = __version__) -> bool:
    return parse_version(remote) > parse_version(local)


def install_kind() -> str:
    """'installer' (instalado com o setup), 'portable' (exe avulso) ou 'source' (Python)."""
    if not getattr(sys, "frozen", False):
        return "source"
    exe_dir = Path(sys.executable).resolve().parent
    return "installer" if any(exe_dir.glob("unins*.exe")) else "portable"


def _official(url: str) -> bool:
    return bool(re.match(rf"^https://{re.escape(OFFICIAL_HOST)}/downloads/sdr-tool/[A-Za-z0-9_.-]+$", url))


def check(kind: str | None = None, base_url: str = UPDATE_URL, timeout: float = 10.0,
          allow_test_host: bool = False) -> UpdateInfo | None:
    """Retorna UpdateInfo se houver versão nova publicada; None se estiver atualizado."""
    kind = kind or install_kind()
    q = f"?product={PRODUCT}&platform=windows-x64" + (f"&kind={kind}" if kind in ("installer", "portable") else "")
    req = urllib.request.Request(base_url + q, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        raise UpdateError(f"Não foi possível consultar {OFFICIAL_HOST}: {e}") from e
    if data.get("product") != PRODUCT or data.get("status") != "available" or not data.get("version"):
        return None
    if not is_newer(data["version"]):
        return None
    files = [f for f in data.get("files", []) if allow_test_host or _official(f.get("url", ""))]
    f = next((x for x in files if x.get("kind") == kind), None)
    return UpdateInfo(data["version"], data.get("date") or "", data.get("notes") or "",
                      data.get("page") or f"https://{OFFICIAL_HOST}/sdr", f)


def download(info: UpdateInfo, progress=None, dest_dir: str | None = None, timeout: float = 30.0) -> Path:
    f = info.file
    if not f:
        raise UpdateError("Não há pacote para este tipo de instalação.")
    size, sha = int(f["size"]), str(f["sha256"]).lower()
    if not re.fullmatch(r"[0-9a-f]{64}", sha) or size <= 0:
        raise UpdateError("Dados do pacote inválidos.")
    name = os.path.basename(f["name"])
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", name):
        raise UpdateError("Nome de arquivo inválido.")
    target = Path(dest_dir or tempfile.mkdtemp(prefix="pt2vhf-sdr-")) / name
    req = urllib.request.Request(f["url"], headers={"User-Agent": USER_AGENT})
    h = hashlib.sha256()
    got = 0
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r, open(target, "wb") as out:
            while True:
                chunk = r.read(1 << 16)
                if not chunk:
                    break
                out.write(chunk)
                h.update(chunk)
                got += len(chunk)
                if got > size:
                    raise UpdateError("Arquivo maior que o esperado.")
                if progress:
                    progress(got, size)
    except UpdateError:
        target.unlink(missing_ok=True)
        raise
    except Exception as e:  # noqa: BLE001
        target.unlink(missing_ok=True)
        raise UpdateError(f"Falha no download: {e}") from e
    if got != size or h.hexdigest() != sha:
        target.unlink(missing_ok=True)
        raise UpdateError("Arquivo corrompido (tamanho ou SHA-256 não conferem). Nada foi instalado.")
    return target


def apply(path: Path, kind: str) -> None:
    """Inicia a instalação. O chamador deve encerrar o programa logo em seguida."""
    if sys.platform != "win32":
        raise UpdateError("Atualização automática disponível apenas no Windows.")
    if kind == "installer":
        subprocess.Popen([str(path), "/SILENT", "/CLOSEAPPLICATIONS", "/RESTARTAPPLICATIONS"], close_fds=True)
        return
    exe = Path(sys.executable).resolve()
    script = Path(tempfile.gettempdir()) / "pt2vhf-sdr-update.cmd"
    script.write_text(
        "@echo off\r\n"
        "ping 127.0.0.1 -n 3 > nul\r\n"
        f':retry\r\ncopy /Y "{path}" "{exe}" > nul || (ping 127.0.0.1 -n 2 > nul & goto retry)\r\n'
        f'start "" "{exe}"\r\n'
        'del "%~f0"\r\n', encoding="ascii", errors="ignore")
    subprocess.Popen(["cmd", "/c", str(script)], close_fds=True, creationflags=0x08000000)
