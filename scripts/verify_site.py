#!/usr/bin/env python3
"""Confere no ar (www.pt2vhf.com) a publicação do PT2VHF SDR Tool, sem inflar os contadores.

- /sdr responde com a página do produto;
- update.php?product=sdr anuncia a versão esperada com os dois pacotes Windows;
- cada pacote é baixado inteiro com "Range: bytes=0-" (retomadas não contam no download.php)
  e confere tamanho e SHA-256 com o manifesto.
Uso: python3 scripts/verify_sdr_live.py X.Y.Z [--wait]
"""
import argparse
import hashlib
import json
import sys
import time
import urllib.request

BASE = "https://www.pt2vhf.com"
HEADERS = {"User-Agent": "PT2VHF-GitHub-Release-Verification/sdr", "Cache-Control": "no-cache"}


def get(url, extra=None, timeout=60):
    req = urllib.request.Request(url, headers={**HEADERS, **(extra or {})})
    return urllib.request.urlopen(req, timeout=timeout)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("version")
    ap.add_argument("--wait", action="store_true")
    args = ap.parse_args()
    tries = 40 if args.wait else 1
    data = None
    for attempt in range(tries):
        try:
            with get(f"{BASE}/update.php?product=sdr&platform=windows-x64&t={time.time():.0f}") as r:
                data = json.loads(r.read().decode("utf-8"))
            kinds = {f.get("kind") for f in data.get("files", [])}
            if data.get("status") == "available" and data.get("version") == args.version and kinds >= {"installer", "portable"}:
                break
            print(f"aguardando implantação: status={data.get('status')} versão={data.get('version')} pacotes={sorted(kinds)}")
        except Exception as e:  # noqa: BLE001
            print(f"aguardando implantação: {e}")
        if attempt == tries - 1:
            sys.exit("Publicação não confirmada no endereço público")
        time.sleep(20)
    with get(f"{BASE}/sdr") as r:
        page = r.read().decode("utf-8", "replace")
        assert r.status == 200 and 'data-program="sdr"' in page, "página /sdr ausente"
    with get(f"{BASE}/updates.json?t={time.time():.0f}") as r:
        manifest = json.loads(r.read().decode("utf-8"))
        assert manifest["products"]["sdr"]["version"] == args.version
    for f in data["files"]:
        h, n = hashlib.sha256(), 0
        with get(f["url"], {"Range": "bytes=0-"}, timeout=600) as r:
            assert r.status in (200, 206), f"{f['name']}: HTTP {r.status}"
            for block in iter(lambda: r.read(1 << 20), b""):
                h.update(block)
                n += len(block)
        assert n == f["size"] and h.hexdigest() == f["sha256"], f"{f['name']}: tamanho/SHA-256 divergentes"
        print(f"OK {f['name']}: {n} bytes, sha256 conferido")
    print("SDR_LIVE_VERIFIED=1")


if __name__ == "__main__":
    main()
