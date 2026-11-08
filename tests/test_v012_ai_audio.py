"""Regressões de IA neural e transcrição offline da v0.12.0."""
import threading
import time
from types import SimpleNamespace

import numpy as np

from pt2vhf.neural_audio import FRAME, NeuralAudioWorker, VOICE_MODES
from pt2vhf.live_caption import LiveCaptionWorker, local_model_path, model_installed


class FakeRNNoise:
    def __init__(self):
        self.calls = 0

    def denoise_chunk(self, pcm, partial=False):
        assert pcm.shape[0] == 1 and pcm.shape[1] % FRAME == 0
        assert pcm.dtype == np.int16
        self.calls += 1
        for i in range(0, pcm.shape[1], FRAME):
            # A biblioteca real devolve floats [-1,1], formato verificado.
            yield np.array([0.91]), pcm[:, i:i + FRAME].astype(np.float32) / 65536.0


def test_neural_stream_mixing_and_frame_buffering():
    backend = FakeRNNoise()
    output, done = [], threading.Event()

    def capture(samples):
        output.append(samples.copy())
        if sum(len(x) for x in output) >= FRAME * 2:
            done.set()

    worker = NeuralAudioWorker(capture, backend=backend, strength=0.8)
    try:
        assert worker.feed(np.full(FRAME // 2, 0.4, np.float32))
        assert worker.feed(np.full(FRAME // 2, 0.4, np.float32))
        assert worker.feed(np.full(FRAME, 0.4, np.float32))
        assert done.wait(5), "worker não processou 2 quadros"
        audio = np.concatenate(output)
        assert audio.shape == (FRAME * 2,)
        # Mix: 20% sinal seco 0.4 + 80% denoised 0.2 = 0.24.
        assert np.allclose(audio, 0.24, atol=0.004)
        assert worker.processed_frames == 2
        assert backend.calls >= 1
    finally:
        worker.stop()


def test_digital_and_wfm_are_not_filtered():
    for mode in ("WFM", "CW", "RAW"):
        assert mode not in VOICE_MODES
    output, done = [], threading.Event()
    worker = NeuralAudioWorker(lambda x: (output.append(x.copy()), done.set()),
                               backend=FakeRNNoise())
    try:
        sample = np.linspace(-0.5, 0.5, 97, dtype=np.float32)
        assert worker.feed(sample, "WFM")
        assert done.wait(5)
        assert np.array_equal(output[0], sample)
        assert worker.processed_frames == 0
    finally:
        worker.stop()


def test_neural_input_queue_drops_stale_audio_without_rf_block():
    gate = threading.Event()
    entered = threading.Event()

    class SlowBackend(FakeRNNoise):
        def denoise_chunk(self, pcm, partial=False):
            entered.set()
            gate.wait(5)
            yield from super().denoise_chunk(pcm, partial=partial)

    worker = NeuralAudioWorker(lambda _: None, backend=SlowBackend(), max_pending=2)
    try:
        worker.feed(np.full(FRAME, 0.1, np.float32))
        assert entered.wait(5)
        start = time.monotonic()
        for _ in range(30):
            worker.feed(np.full(FRAME, 0.1, np.float32))
        assert time.monotonic() - start < 1.0
        assert worker.dropped > 0
        assert worker.queue_depth <= 2
    finally:
        gate.set()
        worker.stop()


def test_whisper_model_is_explicitly_cached(monkeypatch, tmp_path):
    import pt2vhf.live_caption as module
    monkeypatch.setattr(module, "config_dir", lambda: tmp_path)
    assert not model_installed("tiny")
    path = local_model_path("tiny")
    assert path.parent.name == "models"
    path.mkdir(parents=True)
    (path / "model.bin").write_bytes(b"model")
    (path / "config.json").write_text("{}")
    assert model_installed("tiny")
    import pytest
    with pytest.raises(ValueError):
        local_model_path("../../bad")


def test_live_caption_uses_injected_model_without_download():
    finished = threading.Event()
    data = []
    errors = []

    class Model:
        def transcribe(self, audio, language=None, vad_filter=False, beam_size=0):
            assert len(audio) == 32_000  # 48k -> 16k (2 segundos)
            assert vad_filter and beam_size == 1
            return [SimpleNamespace(text="PT2VHF, teste de áudio")], SimpleNamespace(language="pt")

    worker = LiveCaptionWorker(
        on_result=lambda *args: (data.append(args), finished.set()),
        on_error=errors.append, sample_rate=48000, seconds=2.0,
        model=Model(), language="pt", meta_provider=lambda: (145_570_000, "NFM"))
    try:
        worker.feed(np.full(96_000, 0.3, np.float32))
        assert finished.wait(5)
        stamp, text, calls, lang, meta = data[0]
        assert "PT2VHF" in text
        assert "PT2VHF" in calls
        assert lang == "pt"
        assert meta == (145_570_000, "NFM")
        assert not errors
    finally:
        worker.stop()


def test_ui_exposes_neural_and_local_whisper_controls(qt_lifecycle):
    from pt2vhf.ui.panels import AudioPanel
    from pt2vhf.ui.live_captions_panel import LiveCaptionsPanel
    from pt2vhf.config import DEFAULTS
    cfg = dict(DEFAULTS)
    audio = AudioPanel(cfg)
    caption = LiveCaptionsPanel(cfg)
    try:
        assert audio.neural.text().startswith("IA neural")
        assert audio.neural_strength.value() == 80
        assert caption.download.text() == "Baixar modelo"
        assert not caption.refresh_model_status() or caption.model.currentData() == "tiny"
    finally:
        audio.close()
        caption.close()
