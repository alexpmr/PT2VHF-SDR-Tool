"""Native Linux/macOS packaging contracts and isolated archive smoke tests."""
from __future__ import annotations

import hashlib
import platform
import sys
import tarfile
from pathlib import Path

import pytest

from packaging import package_unix as pkg


def test_unix_architectures_and_version():
    assert pkg.arch_names("x86_64") == ("x86_64", "amd64")
    assert pkg.arch_names("aarch64") == ("arm64", "arm64")
    assert pkg.arch_names("arm64") == ("arm64", "arm64")
    with pytest.raises(ValueError):
        pkg.arch_names("mips")
    assert pkg.source_version() == "1.0.0"


def test_packaging_fails_closed_when_banner_is_absent(tmp_path):
    bundle = tmp_path / "fake-native"
    bundle.mkdir()
    with pytest.raises(FileNotFoundError, match="splash"):
        pkg.assert_banner(bundle)


def test_native_archive_and_sha256(tmp_path, monkeypatch):
    bundle = tmp_path / "PT2VHF-SDR-Tool"
    bundle.mkdir()
    (bundle / "pt2vhf-sdr").write_text("fixture", encoding="utf-8")
    release = tmp_path / "release"
    release.mkdir()
    tgz = pkg.compress_tgz(bundle, release / "PT2VHF-SDR-Tool.tgz")
    with tarfile.open(tgz, "r:gz") as tar:
        assert f"{bundle.name}/pt2vhf-sdr" in tar.getnames()
    monkeypatch.setattr(pkg, "RELEASE", release)
    sha_file = pkg.checksums([tgz])
    sha, filename = sha_file.read_text().strip().split("  ")
    assert filename == tgz.name
    assert sha == hashlib.sha256(tgz.read_bytes()).hexdigest()


@pytest.mark.skipif(sys.platform != "linux", reason="Needs Linux dpkg-deb")
def test_deb_and_tgz_contain_bundle_and_desktop_launcher(tmp_path, monkeypatch):
    if not pkg.shutil.which("dpkg-deb"):
        pytest.skip("dpkg-deb not installed")
    dist = tmp_path / "dist"
    bundle = dist / pkg.APP_ID
    bundle.mkdir(parents=True)
    exe = bundle / pkg.APP_ID
    exe.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    exe.chmod(0o755)
    source = bundle / "pt2vhf" / "assets" / "branding"
    source.mkdir(parents=True)
    # Fake JPEG payload is intentionally NOT used for a distributable build:
    # this checks package layout, not the real PT2VHF splash image quality.
    (source / "welcome-banner.jpg").write_bytes(b"synthetic-test-artifact" * 1600)
    monkeypatch.setattr(pkg, "DIST", dist)
    monkeypatch.setattr(pkg, "RELEASE", tmp_path / "release")
    artifacts = pkg.linux_packages("1.0.0", platform.machine())
    assert {x.suffix for x in artifacts} == {".deb", ".tgz"}
    assert all(x.stat().st_size > 300 for x in artifacts)
    assert pkg.checksums(artifacts).is_file()
