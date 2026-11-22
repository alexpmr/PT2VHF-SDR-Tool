"""OTA contract regression tests: synthetic manifest and redirect URLs only.

No network, no real installer and no claim of completed Windows OTA.
"""
import urllib.request

import pytest

from pt2vhf import updater


VERSION = "0.13.1"
NAME = f"PT2VHF-SDR-Tool-v{VERSION}-Win11-x64-Setup.exe"
OFFICIAL = f"https://www.pt2vhf.com/download.php?product=sdr&file={NAME}"
GITHUB = f"https://github.com/alexpmr/PT2VHF-SDR-Tool/releases/download/v{VERSION}/{NAME}"
CDN = "https://release-assets.githubusercontent.com/github-production-release-asset/123?token=signed"


def test_site_manifest_contract_selects_installer_for_ota():
    manifest = {
        "schema": 1,
        "product": "sdr",
        "status": "available",
        "version": VERSION,
        "date": "2026-11-10",
        "notes": "OTA maintenance",
        "files": [{"kind": "installer", "name": NAME, "url": OFFICIAL,
                   "size": 4096, "sha256": "a" * 64}],
    }
    info = updater.select_update(manifest, "installer", current="0.13.0")
    assert info is not None and info.file is not None
    assert info.file["url"] == OFFICIAL
    assert info.allow_test_host is False


@pytest.mark.parametrize("url,allowed", [
    (OFFICIAL, True),
    (f"https://www.pt2vhf.com/downloads/sdr-tool/{NAME}", True),
    (OFFICIAL.replace("product=sdr", "product=sat"), False),
    (OFFICIAL + "&file=" + NAME, False),
    (OFFICIAL + "&next=https://evil.invalid", False),
    (OFFICIAL.replace("www.pt2vhf.com", "www.pt2vhf.com.evil.invalid"), False),
    (OFFICIAL.replace("https://", "http://"), False),
    (OFFICIAL.replace("download.php", "redirect.php"), False),
    (OFFICIAL + "#fragment", False),
    (f"https://www.pt2vhf.com/download.php?file={NAME}&product=sdr", True),
])
def test_canonical_site_download_url(url, allowed):
    assert updater.is_official(url, NAME) is allowed


def test_expected_redirect_chain_and_manifest_hash_policy():
    r = updater._PackageRedirect(NAME, VERSION)
    first = r.redirect_request(urllib.request.Request(OFFICIAL), None, 302,
                               "Found", {}, GITHUB)
    assert first.full_url == GITHUB
    second = r.redirect_request(urllib.request.Request(GITHUB), None, 302,
                                "Found", {}, CDN)
    assert second.full_url == CDN


@pytest.mark.parametrize("start,target", [
    (OFFICIAL, "https://evil.invalid/a.exe"),
    (OFFICIAL, CDN),  # Cannot jump directly to a signed asset CDN.
    (OFFICIAL, GITHUB.replace("v0.13.1", "v0.13.0")),
    (OFFICIAL, GITHUB.replace("/alexpmr/", "/attacker/")),
    (OFFICIAL, GITHUB.replace("https://", "http://")),
    (GITHUB, "https://evil.invalid/asset"),
    (GITHUB, "https://github.com/alexpmr/PT2VHF-SDR-Tool/releases/download/v0.13.0/x.exe"),
    (GITHUB, "http://release-assets.githubusercontent.com/asset"),
])
def test_reject_untrusted_redirects(start, target):
    r = updater._PackageRedirect(NAME, VERSION)
    with pytest.raises(updater.UpdateError, match="não autorizado|fora da release"):
        r.redirect_request(urllib.request.Request(start), None, 302, "Found", {}, target)


def test_disallow_download_from_forged_info_before_network(tmp_path):
    forged = updater.UpdateInfo(
        version=VERSION, date="", notes="", page="",
        file={"name": NAME, "url": "https://evil.invalid/download.exe",
              "size": 20, "sha256": "a" * 64})
    with pytest.raises(updater.UpdateError, match="fora do site oficial"):
        updater.download(forged, dest_dir=str(tmp_path))
