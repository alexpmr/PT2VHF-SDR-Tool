"""Atualização (OTA) no padrão dos programas PT2VHF (como o Sat Tool).

- manifesto no site oficial, downloads por redirecionamento restrito à release PT2VHF;
- verificação automática; download com tamanho e SHA-256 obrigatórios (falha fechada);
- a instalação é feita por um auxiliar externo (scripts/apply-update.ps1) depois que o programa fecha:
  instalador em modo silencioso ou troca do EXE portátil (com cópia de segurança), e o programa reabre;
- o resultado da última atualização é mostrado na abertura seguinte.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit, parse_qsl

from . import __version__

ORIGIN = "https://www.pt2vhf.com"
OFFICIAL_HOST = "www.pt2vhf.com"
PRODUCT = "sdr"
UPDATE_URL = ORIGIN + "/update.php"
WEB_URL = ORIGIN + "/sdr"
DOWNLOAD_PREFIX = "/downloads/sdr-tool/"
USER_AGENT = f"PT2VHF-SDR-Tool/{__version__}"
HASH_RE = re.compile(r"[0-9a-f]{64}")
VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")
MAX_MANIFEST_BYTES = 2_000_000
MAX_PACKAGE_BYTES = 600 * 1024 * 1024
RESULT_FILE = "PT2VHF-SDR-Tool-update-result.txt"


class UpdateError(Exception):
    pass


@dataclass
class UpdateInfo:
    version: str
    date: str
    notes: str
    page: str
    file: dict | None
    allow_test_host: bool = False
    unavailable_reason: str = ""


def parse_version(v: str) -> tuple[int, ...]:
    m = re.match(r"^v?(\d+)\.(\d+)\.(\d+)", str(v or "").strip())
    return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)


def is_newer(remote: str, local: str = __version__) -> bool:
    return parse_version(remote) > parse_version(local)


def install_kind(exe_path: Path | None = None, frozen: bool | None = None) -> str:
    """'installer', 'portable' ou 'source' (rodando pelo Python: nunca se atualiza sozinho)."""
    frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    if not frozen:
        return "source"
    if sys.platform != "win32":
        # Native Linux/macOS bundles must never execute a Windows .exe.
        # Updates remain manual until an OS-specific updater is tested.
        return "manual"
    exe = (exe_path or Path(sys.executable)).resolve()
    if (exe.parent / "portable.flag").exists() or exe.stem.casefold().endswith("-portable"):
        return "portable"
    return "installer"


def is_official(url: str, name: str) -> bool:
    """Accept canonical site files and the exact official download.php contract."""
    try:
        if not isinstance(url, str) or not isinstance(name, str):
            return False
        if not re.fullmatch(r"[A-Za-z0-9_.-]+\.exe", name, re.IGNORECASE):
            return False
        u = urlsplit(url)
        if (u.scheme != "https" or u.netloc != OFFICIAL_HOST or u.fragment
                or "%" in u.path or u.username or u.password):
            return False
        if u.path == DOWNLOAD_PREFIX + name and not u.query:
            return True
        if u.path == "/download.php":
            return sorted(parse_qsl(u.query, keep_blank_values=True)) == sorted(
                [("product", PRODUCT), ("file", name)])
        return False
    except (TypeError, ValueError, AttributeError):
        return False


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        raise UpdateError("Redirecionamento bloqueado fora do fluxo oficial.")


class _PackageRedirect(urllib.request.HTTPRedirectHandler):
    """Allow only site -> matching GitHub release -> GitHub asset CDN."""
    def __init__(self, name: str, version: str):
        super().__init__()
        self.name = name
        self.version = version

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        old, target = urlsplit(req.full_url), urlsplit(newurl)
        if target.scheme != "https" or target.username or target.password or target.fragment:
            raise UpdateError("Destino de atualização inseguro ou não autorizado.")
        expected = (f"/alexpmr/PT2VHF-SDR-Tool/releases/download/"
                    f"v{self.version.lstrip('v')}/{self.name}")
        from_site = (is_official(req.full_url, self.name)
                     and target.netloc == "github.com"
                     and target.path == expected and not target.query)
        from_release = (old.scheme == "https" and old.netloc == "github.com"
                        and old.path == expected and not old.query
                        and target.netloc in ("release-assets.githubusercontent.com",
                                              "objects.githubusercontent.com")
                        and bool(target.path))
        if not (from_site or from_release):
            raise UpdateError("Redirecionamento fora da release oficial PT2VHF.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_opener = urllib.request.build_opener(_NoRedirect)


def select_update(manifest: dict, kind: str, current: str = __version__,
                  allow_test_host: bool = False) -> UpdateInfo | None:
    """Valida a resposta do update.php e escolhe o pacote desta instalação."""
    if not isinstance(manifest, dict) or manifest.get("schema", 1) != 1:
        raise UpdateError("Manifesto do site PT2VHF inválido")
    if manifest.get("product") != PRODUCT:
        raise UpdateError("Manifesto não pertence ao PT2VHF SDR Tool")
    if manifest.get("status") != "available" or not manifest.get("version"):
        return None
    version = str(manifest["version"])
    if not VERSION_RE.fullmatch(version) or not is_newer(version, current):
        return None
    chosen = None
    reason = f"O site não oferece pacote de atualização para '{kind}' nesta versão."
    for f in manifest.get("files") or []:
        if not isinstance(f, dict) or f.get("kind") != kind:
            continue
        name, url, size, sha = f.get("name", ""), f.get("url", ""), f.get("size"), str(f.get("sha256", ""))
        if not (allow_test_host or is_official(url, name)):
            reason = "URL do pacote incompatível com a política segura de atualização."
            continue
        if type(size) is not int or not 0 < size <= MAX_PACKAGE_BYTES or not HASH_RE.fullmatch(sha):
            reason = "Pacote anunciado sem tamanho e SHA-256 válidos."
            continue
        chosen = f
        reason = ""
        break
    return UpdateInfo(version, str(manifest.get("date") or ""), str(manifest.get("notes") or ""),
                      str(manifest.get("page") or WEB_URL), chosen, allow_test_host, reason)


def check(kind: str | None = None, base_url: str = UPDATE_URL, timeout: float = 20.0,
          allow_test_host: bool = False) -> UpdateInfo | None:
    kind = kind or install_kind()
    url = f"{base_url}?product={PRODUCT}&platform=windows-x64" + (f"&kind={kind}" if kind in ("installer", "portable") else "")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with _opener.open(req, timeout=timeout) as r:
            raw = r.read(MAX_MANIFEST_BYTES + 1)
    except UpdateError:
        raise
    except Exception as e:  # noqa: BLE001
        raise UpdateError(f"Não foi possível consultar {OFFICIAL_HOST}: {e}") from e
    if len(raw) > MAX_MANIFEST_BYTES:
        raise UpdateError("Manifesto excede o limite de tamanho")
    try:
        data = json.loads(raw.decode("utf-8"))
    except ValueError as e:
        raise UpdateError("Resposta inválida do site") from e
    return select_update(data, kind, allow_test_host=allow_test_host)


def download(info: UpdateInfo, progress=None, dest_dir: str | None = None, timeout: float = 60.0) -> Path:
    f = info.file
    if not f:
        raise UpdateError("Não há pacote para este tipo de instalação.")
    size, sha, name = int(f["size"]), str(f["sha256"]).lower(), os.path.basename(f["name"])
    if not HASH_RE.fullmatch(sha) or size <= 0 or not re.fullmatch(r"[A-Za-z0-9_.-]+", name):
        raise UpdateError("Atualização sem tamanho e SHA-256 verificáveis; bloqueada.")
    target = Path(dest_dir or tempfile.mkdtemp(prefix="pt2vhf_sdr_update_")) / name
    if not info.allow_test_host and not is_official(f["url"], name):
        raise UpdateError("Pacote fora do site oficial PT2VHF.")
    opener = _opener if info.allow_test_host else urllib.request.build_opener(_PackageRedirect(name, info.version))
    req = urllib.request.Request(f["url"], headers={"User-Agent": USER_AGENT})
    h, got = hashlib.sha256(), 0
    try:
        with opener.open(req, timeout=timeout) as r, open(target, "wb") as out:
            declared = r.headers.get("Content-Length")
            if declared and int(declared) != size:
                raise UpdateError("Tamanho do pacote diverge do manifesto do site.")
            while True:
                chunk = r.read(1 << 17)
                if not chunk:
                    break
                got += len(chunk)
                if got > size:
                    raise UpdateError("Pacote excede o tamanho publicado.")
                h.update(chunk)
                out.write(chunk)
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
        raise UpdateError("SHA-256 ou tamanho não confere: atualização abortada. Nada foi instalado.")
    return target


def helper_script() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    return base / "scripts" / "apply-update.ps1"


def update_script_args(helper: Path, *, pid: int, package: Path, destination: Path, exe: Path,
                       portable: bool, version: str = "", ready_file: Path | None = None) -> list:
    ps = Path(os.environ.get("SYSTEMROOT", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    return [str(ps), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden",
            "-File", str(helper), "-WaitPid", str(pid), "-Package", str(package), "-Destination", str(destination),
            "-Executable", str(exe), "-Mode", "Portable" if portable else "Setup", "-Version", str(version),
            *(["-ReadyFile", str(ready_file)] if ready_file is not None else [])]


def apply(path: Path, kind: str, version: str = "") -> None:
    """Inicia o auxiliar externo. O programa deve fechar logo em seguida."""
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        raise UpdateError("A atualização automática só funciona nos executáveis Windows.")
    if path.suffix.lower() != ".exe" or not path.is_file():
        raise UpdateError("Pacote verificado não encontrado.")
    script = helper_script()
    if not script.is_file():
        raise UpdateError("Auxiliar de atualização ausente do pacote.")
    helper = path.parent / "apply-update.ps1"  # fora da pasta temporária do EXE portátil
    shutil.copy2(script, helper)
    exe = Path(sys.executable).resolve()
    # Unique acknowledgement ensures the PowerShell script actually STARTED,
    # not merely that CreateProcess returned successfully.
    ready = path.parent / ("ota-helper-ready-" + uuid.uuid4().hex + ".txt")
    args = update_script_args(helper, pid=os.getpid(), package=path, destination=exe.parent, exe=exe,
                              portable=(kind == "portable"), version=version, ready_file=ready)
    flags = (getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
             | getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0))
    try:
        try:
            worker = subprocess.Popen(args, close_fds=True, creationflags=flags)
        except OSError:
            worker = subprocess.Popen(
                args, close_fds=True,
                creationflags=flags & ~getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0))
    except OSError as exc:
        raise UpdateError(f"Não foi possível iniciar o auxiliar OTA: {exc}") from exc
    try:
        until = time.monotonic() + 12.0
        while time.monotonic() < until:
            if ready.is_file():
                if ready.read_text(encoding="utf-8-sig").strip() == "READY":
                    return
                raise UpdateError("Auxiliar OTA respondeu incorretamente. O aplicativo permanecerá aberto.")
            if worker.poll() is not None:
                raise UpdateError("O PowerShell encerrou antes de iniciar a atualização. "
                                  "Consulte PT2VHF-SDR-Tool-ota-helper.log em %TEMP%.")
            time.sleep(0.15)
        raise UpdateError("O auxiliar OTA não confirmou inicialização em 12 segundos; "
                          "o aplicativo permanecerá aberto. Consulte o log OTA em %TEMP%.")
    finally:
        ready.unlink(missing_ok=True)


def read_update_result(temp_dir: Path | None = None) -> tuple[str, str, str] | None:
    """(status, versão, detalhe) da última atualização externa; apaga o arquivo depois de ler."""
    path = Path(temp_dir or tempfile.gettempdir()) / RESULT_FILE
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
        path.unlink()
    except OSError:
        return None
    lines += ["", "", ""]
    return lines[0].strip(), lines[1].strip(), lines[2].strip()
