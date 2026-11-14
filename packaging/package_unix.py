"""Package native Linux .deb/.tgz and macOS .app/.dmg for PT2VHF SDR Tool.

Requires PyInstaller onedir output built on the target OS/architecture:
    pyinstaller --noconfirm packaging/pt2vhf_unix.spec
    python packaging/package_unix.py --platform linux
    python packaging/package_unix.py --platform macos

A local source checkout and the original user-supplied splash are mandatory.
No cross-compilation, signing or automatic deployment is claimed.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
RELEASE = ROOT / "release"
APP_ID = "pt2vhf-sdr"
TITLE = "PT2VHF SDR Tool"


def arch_names(machine: str) -> tuple[str, str]:
    if machine.lower() in ("x86_64", "amd64"):
        return "x86_64", "amd64"
    if machine.lower() in ("aarch64", "arm64"):
        return "arm64", "arm64"
    raise ValueError(f"Unsupported architecture: {machine}")


def source_version() -> str:
    sys.path.insert(0, str(ROOT))
    from pt2vhf import __version__
    if not __version__ or any(c not in "0123456789." for c in __version__):
        raise ValueError("Invalid package version")
    return __version__


def assert_banner(source: Path) -> Path:
    found = [p for p in source.rglob("welcome-banner.jpg")
             if p.as_posix().endswith("pt2vhf/assets/branding/welcome-banner.jpg")]
    if not found or found[0].stat().st_size < 25000:
        raise FileNotFoundError("Original PT2VHF splash is missing from assembled bundle")
    return found[0]


def compress_tgz(source: Path, output: Path) -> Path:
    with tarfile.open(output, "w:gz", dereference=False) as tar:
        tar.add(source, arcname=source.name, recursive=True)
    return output


def checksums(files: list[Path]) -> Path:
    listing = RELEASE / "SHA256SUMS.txt"
    with listing.open("w", encoding="ascii") as out:
        for file in files:
            with file.open("rb") as handle:
                digest = hashlib.file_digest(handle, "sha256").hexdigest()
            out.write(f"{digest}  {file.name}\n")
    return listing


def linux_packages(version: str, arch: str) -> list[Path]:
    if sys.platform != "linux":
        raise RuntimeError("Linux packages must be built on Linux")
    if not shutil.which("dpkg-deb"):
        raise FileNotFoundError("dpkg-deb not available")
    normalized, deb_arch = arch_names(arch)
    app = DIST / APP_ID
    assert (app / APP_ID).is_file()
    assert_banner(app)
    RELEASE.mkdir(exist_ok=True)
    base = f"PT2VHF-SDR-Tool-v{version}-Linux-{normalized}"
    tgz = RELEASE / f"{base}.tgz"
    with tempfile.TemporaryDirectory(prefix="pt2vhf-package-") as folder:
        work = Path(folder)
        portable = work / "PT2VHF-SDR-Tool"
        shutil.copytree(app, portable, symlinks=True)
        shutil.copy2(ROOT / "packaging/pt2vhf.png", portable / "pt2vhf.png")
        (portable / "README.txt").write_text(
            "Run ./pt2vhf-sdr from a graphical Linux desktop.\n"
            "RTL-SDR USB devices need appropriate udev permissions.\n"
            "Official site: https://www.pt2vhf.com\n", encoding="utf-8")
        compress_tgz(portable, tgz)

        debroot = work / "debroot"
        target = debroot / "opt" / APP_ID
        shutil.copytree(app, target, symlinks=True)
        launch = debroot / "usr/bin" / APP_ID
        launch.parent.mkdir(parents=True)
        launch.write_text(
            "#!/bin/sh\nexec /opt/pt2vhf-sdr/pt2vhf-sdr \"$@\"\n",
            encoding="utf-8")
        launch.chmod(0o755)
        icons = debroot / "usr/share/pixmaps"
        icons.mkdir(parents=True)
        shutil.copy2(ROOT / "packaging/pt2vhf.png", icons / (APP_ID + ".png"))
        applications = debroot / "usr/share/applications"
        applications.mkdir(parents=True)
        (applications / (APP_ID + ".desktop")).write_text(
            "[Desktop Entry]\nType=Application\nName=PT2VHF SDR Tool\n"
            "Comment=Software-defined radio receiver with waterfall\n"
            "Exec=/usr/bin/pt2vhf-sdr\nIcon=pt2vhf-sdr\nTerminal=false\n"
            "Categories=Network;AudioVideo;\nStartupNotify=true\n", encoding="utf-8")
        control = debroot / "DEBIAN/control"
        control.parent.mkdir(parents=True)
        size = (sum(p.stat().st_size for p in target.rglob("*")
                    if p.is_file()) + 1023) // 1024
        control.write_text(
            f"Package: pt2vhf-sdr-tool\nVersion: {version}\n"
            f"Architecture: {deb_arch}\nSection: hamradio\nPriority: optional\n"
            "Maintainer: PT2VHF <info@pt2vhf.com>\n"
            "Homepage: https://www.pt2vhf.com\n"
            f"Installed-Size: {size}\n"
            "Depends: libc6, libegl1, libgl1, libxcb1, libxkbcommon-x11-0, libusb-1.0-0, libportaudio2\n"
            "Description: PT2VHF SDR Tool radio and spectrum receiver\n"
            " Desktop software-defined radio application for RTL-SDR and other receivers.\n",
            encoding="utf-8")
        deb = RELEASE / f"pt2vhf-sdr-tool_{version}_{deb_arch}.deb"
        subprocess.run(["dpkg-deb", "--root-owner-group", "--build",
                        str(debroot), str(deb)], check=True)
        subprocess.run(["dpkg-deb", "--info", str(deb)], check=True)
        with tempfile.TemporaryDirectory(prefix="pt2vhf-verify-") as dest:
            subprocess.run(["dpkg-deb", "-x", str(deb), dest], check=True)
            assert_banner(Path(dest) / "opt" / APP_ID)
            assert (Path(dest) / "usr/bin" / APP_ID).exists()
    return [deb, tgz]


def macos_packages(version: str, arch: str) -> list[Path]:
    if sys.platform != "darwin":
        raise RuntimeError("macOS packages must be built on macOS")
    if not shutil.which("hdiutil"):
        raise FileNotFoundError("macOS hdiutil unavailable")
    normalized, _ = arch_names(arch)
    app = DIST / (TITLE + ".app")
    assert (app / "Contents/Info.plist").is_file()
    assert_banner(app)
    RELEASE.mkdir(exist_ok=True)
    base = f"PT2VHF-SDR-Tool-v{version}-macOS-{normalized}"
    tarball = RELEASE / (base + ".app.tgz")
    dmg = RELEASE / (base + ".dmg")
    compress_tgz(app, tarball)
    with tempfile.TemporaryDirectory(prefix="pt2vhf-mac-") as temp:
        staging = Path(temp) / TITLE
        staging.mkdir()
        shutil.copytree(app, staging / app.name, symlinks=True)
        (staging / "Applications").symlink_to("/Applications", target_is_directory=True)
        (staging / "README.txt").write_text(
            "Drag PT2VHF SDR Tool.app to Applications.\n"
            "This developer preview is unsigned and not notarized by Apple.\n"
            "Official site: https://www.pt2vhf.com\n",
            encoding="utf-8")
        subprocess.run(["hdiutil", "create", "-volname", TITLE, "-srcfolder",
                        str(staging), "-ov", "-format", "UDZO", str(dmg)], check=True)
        subprocess.run(["hdiutil", "verify", str(dmg)], check=True)
    return [tarball, dmg]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=("linux", "macos"), required=True)
    args = parser.parse_args()
    version = source_version()
    machine = platform.machine()
    generated = (linux_packages(version, machine)
                 if args.platform == "linux"
                 else macos_packages(version, machine))
    sha = checksums(generated)
    for item in [*generated, sha]:
        print(f"PACKAGE_OK {item} ({item.stat().st_size} bytes)", flush=True)


if __name__ == "__main__":
    main()
