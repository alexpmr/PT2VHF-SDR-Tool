"""Decodificadores RS41 embarcados: resolução, licenças e pipeline sintético.

O pipeline sintético prova IQ -> ChannelIQ -> fsk_demod -> rs41mod -> JSON com
os mesmos argumentos do app. Não é homologação com IQ real de radiossonda.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

import pt2vhf.sonde_rx as sonde_rx
from pt2vhf.sonde_synth import FRAME_LEN, crc16, rs41_frame, rs_parity


def _fake_bundle(tmp_path, names=("fsk_demod", "rs41mod")):
    ext = ".exe" if os.name == "nt" else ""
    for n in names:
        p = tmp_path / (n + ext)
        p.write_bytes(b"")
        p.chmod(0o755)
    return tmp_path


def test_bundled_copy_preferred_over_path(tmp_path, monkeypatch):
    folder = _fake_bundle(tmp_path)
    monkeypatch.setattr(sonde_rx, "bundled_decoder_dir", lambda: folder)
    monkeypatch.setattr(sonde_rx.shutil, "which", lambda name: "/usr/bin/" + name)
    path, origin = sonde_rx.locate_binary("rs41mod", "")
    assert origin == "embarcado" and Path(path).parent == folder.resolve()
    # Nome puro igual ao padrão (configuração antiga) também usa a cópia embarcada.
    assert sonde_rx.locate_binary("fsk_demod", "fsk_demod")[1] == "embarcado"


def test_user_path_wins_and_does_not_fall_back(tmp_path, monkeypatch):
    (tmp_path / "b").mkdir()
    folder = _fake_bundle(tmp_path / "b")
    monkeypatch.setattr(sonde_rx, "bundled_decoder_dir", lambda: folder)
    custom = tmp_path / "meu_rs41mod"
    custom.write_bytes(b"")
    assert sonde_rx.locate_binary("rs41mod", str(custom)) == (str(custom.resolve()), "usuário")
    missing = str(tmp_path / "nao_existe" / "rs41mod_x")
    assert sonde_rx.locate_binary("rs41mod", missing) == (None, "usuário")
    with pytest.raises(FileNotFoundError, match="caminho configurado"):
        sonde_rx.find_binary("rs41mod", missing)


def test_no_bundle_falls_back_to_path(monkeypatch):
    monkeypatch.setattr(sonde_rx, "bundled_decoder_dir", lambda: None)
    monkeypatch.setattr(sonde_rx.shutil, "which", lambda name: None)
    assert sonde_rx.locate_binary("fsk_demod") == (None, "PATH")
    with pytest.raises(FileNotFoundError, match="embarcada"):
        sonde_rx.find_binary("fsk_demod")


def test_synthetic_frame_has_valid_crc_and_reed_solomon():
    frame = rs41_frame()
    assert len(frame) == FRAME_LEN
    pos = 0x39
    while pos < FRAME_LEN - 1:
        n = frame[pos + 1]
        assert int.from_bytes(frame[pos + 2 + n:pos + 4 + n], "little") == crc16(frame[pos + 2:pos + 2 + n])
        pos += n + 4
    msg = frame[56:]
    assert frame[8:32] == rs_parity(msg[0::2]) and frame[32:56] == rs_parity(msg[1::2])


def test_packaging_ships_licenses_and_source():
    root = Path(__file__).resolve().parent.parent
    script = (root / "packaging" / "build_sonde_decoders.sh").read_text(encoding="utf-8")
    assert "AUTORX_COMMIT=" in script and "source" in script
    lic = root / "packaging" / "sonde_licenses"
    assert "Version 2.1" in (lic / "LICENSE-LGPL-2.1.txt").read_text(encoding="utf-8")
    readme = (lic / "README-THIRD-PARTY.txt").read_text(encoding="utf-8")
    assert "GPL-3.0" in readme.replace("v3.0", "GPL-3.0") and "LGPL" in readme
    assert "sonde_decoders" in (root / "pt2vhf.spec").read_text(encoding="utf-8")


@pytest.mark.skipif(not all(sonde_rx.locate_binary(n)[0] for n in ("fsk_demod", "rs41mod")),
                    reason="fsk_demod/rs41mod não compilados (packaging/build_sonde_decoders.sh native)")
def test_synthetic_rs41_end_to_end_with_app_arguments():
    frames = sonde_rx.synthetic_pipeline_check()
    assert len(frames) >= 2
    first = frames[0]
    assert first["type"] == "RS41" and first["id"] == "T1234567"
    assert abs(first["lat"] + 23.5) < 1e-3 and abs(first["lon"] + 46.6) < 1e-3
    assert abs(first["alt"] - 12000) < 5
    assert {f["frame"] for f in frames} <= {1000, 1001, 1002, 1003}
