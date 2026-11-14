"""T-0046 @stt (box and server only; needs app/requirements-voice.txt and a local model): the real model transcribes
the pinned fixture with >= 3 of 4 keywords and a real-time factor <= 0.5 (spec §10.8). Skipped where no model is set
up (CI runs the Stub tests in test_t0046_stt*.py)."""
import time
from pathlib import Path

import pytest

from brief import stt

FIXTURE = Path(stt.__file__).parent / "fixtures" / "visit_note_fixture_16k.wav"
KEYWORDS = ("clinic", "manager", "flu", "shingles")


@pytest.mark.stt
def test_real_model_on_fixture(monkeypatch):
    monkeypatch.setenv("LB_STT", "faster-whisper")
    tr, why = stt.get_transcriber()
    if tr is None:
        pytest.skip(f"no local STT model: {why}")
    audio = stt.decode_wav(FIXTURE.read_bytes())
    tr.transcribe(audio[:16000])  # load the model outside the timed run
    t = time.perf_counter()
    text = tr.transcribe(audio)
    dt = time.perf_counter() - t
    rtf = dt / (audio.size / stt.SAMPLE_RATE)
    hits = [k for k in KEYWORDS if k in text.lower()]
    print(f"\nSTT {tr.name}: {dt:.2f}s for {audio.size / stt.SAMPLE_RATE:.2f}s audio, RTF {rtf:.3f}, "
          f"keywords {len(hits)}/4 {hits}\ntranscript: {text}")
    assert len(hits) >= 3, text
    assert rtf <= 0.5, rtf
