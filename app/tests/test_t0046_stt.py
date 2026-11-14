"""T-0046 STT seam (unit, no model, no Streamlit): the pinned fixture; stdlib WAV decode gives float32 at 16 kHz and
refuses anything else; get_transcriber() returns Stub / FasterWhisper / None with a reason; FasterWhisper loads only
from a local directory (offline) and is handed an array, never a path (F-0018 (PyAV path decode fails));
transcribe_bytes() never raises.
Mutations: stt_nofallback (errors propagate), stt_none (off / missing engine still gives a transcriber),
stt_decode (no format checks), stt_offline (model loaded by name, downloads allowed)."""
import hashlib
import io
import sys
import types
import wave
from pathlib import Path

import numpy as np
import pytest

from brief import stt

FIXTURE = Path(stt.__file__).parent / "fixtures" / "visit_note_fixture_16k.wav"
FIXTURE_SHA256 = "25c2054670d34c198ba4d1976a4c20df9d118042f34942d8141e584c079e3f82"


def _wav(rate=16000, ch=1, width=2, frames=1600, value=1000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(ch)
        w.setsampwidth(width)
        w.setframerate(rate)
        sample = int(value).to_bytes(width, "little", signed=width > 1) if width > 1 else bytes([128 + 10])
        w.writeframes(sample * ch * frames)
    return buf.getvalue()


def test_fixture_pinned():
    data = FIXTURE.read_bytes()
    assert hashlib.sha256(data).hexdigest() == FIXTURE_SHA256
    with wave.open(io.BytesIO(data)) as w:
        assert (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (16000, 1, 2)
        assert abs(w.getnframes() / 16000 - 8.27) < 0.01


def test_decode_float32_16k():
    data = FIXTURE.read_bytes()
    a = stt.decode_wav(data)
    assert a.dtype == np.float32 and a.ndim == 1
    with wave.open(io.BytesIO(data)) as w:
        assert a.size == w.getnframes()
    assert 0 < float(np.abs(a).max()) <= 1.0
    s = stt.decode_wav(_wav(ch=2, frames=160, value=16384))  # stereo is mixed down to mono
    assert s.dtype == np.float32 and s.size == 160 and np.allclose(s, 0.5)


@pytest.mark.parametrize("bad", [_wav(rate=44100), _wav(rate=8000), _wav(width=1), _wav(frames=0),
                                 b"RIFF\x00\x00\x00\x00WAVEjunk", b"", b"not audio at all"])
def test_decode_rejects_bad(bad):
    with pytest.raises(stt.AudioError):
        stt.decode_wav(bad)


def test_get_transcriber_config(monkeypatch, tmp_path):
    for k in ("LB_STT", "LB_STT_MODEL", "LB_STT_MODEL_DIR", "LB_STT_STUB_TEXT"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("LB_STT", "off")
    tr, why = stt.get_transcriber()
    assert tr is None and "LB_STT=off" in why
    monkeypatch.setenv("LB_STT", "stub")
    monkeypatch.setenv("LB_STT_STUB_TEXT", "hello clinic")
    tr, why = stt.get_transcriber()
    assert isinstance(tr, stt.Stub) and tr.transcribe(np.zeros(16, np.float32)) == "hello clinic" and why == ""
    monkeypatch.setenv("LB_STT", "bogus")
    assert stt.get_transcriber()[0] is None

    monkeypatch.delenv("LB_STT")  # default engine: faster-whisper
    real_find = stt.importlib.util.find_spec
    monkeypatch.setattr(stt.importlib.util, "find_spec", lambda n: None if n == "faster_whisper" else real_find(n))
    tr, why = stt.get_transcriber()
    assert tr is None and "not installed" in why
    monkeypatch.setattr(stt.importlib.util, "find_spec", lambda n: object())
    monkeypatch.setenv("LB_STT_MODEL_DIR", str(tmp_path / "nowhere"))
    tr, why = stt.get_transcriber()
    assert tr is None and "not found" in why
    (tmp_path / "m").mkdir()
    (tmp_path / "m" / "model.bin").write_bytes(b"x")
    monkeypatch.setenv("LB_STT_MODEL_DIR", str(tmp_path / "m"))
    tr, why = stt.get_transcriber()
    assert isinstance(tr, stt.FasterWhisper) and tr.model == "small.en" and why == ""  # small.en is the default
    monkeypatch.setenv("LB_STT_MODEL", "base.en")  # the swap
    assert stt.get_transcriber()[0].model == "base.en"
    monkeypatch.delenv("LB_STT_MODEL_DIR")
    assert stt.model_dir().name == "faster-whisper-base.en"
    monkeypatch.setenv("LB_STT_MODEL", "large-v3")
    tr, why = stt.get_transcriber()
    assert tr is None and "unknown model" in why


def test_faster_whisper_offline_args(monkeypatch, tmp_path):
    calls = {}

    class FakeModel:
        def __init__(self, path, **kw):
            calls["init"] = (path, kw)

        def transcribe(self, audio, **kw):
            calls["transcribe"] = (audio, kw)
            return iter([types.SimpleNamespace(text=" Met the clinic manager. "), types.SimpleNamespace(text="Flu.")]), None

    monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=FakeModel))
    fw = stt.FasterWhisper("small.en", tmp_path)
    out = fw.transcribe(stt.decode_wav(FIXTURE.read_bytes()))
    assert out == "Met the clinic manager. Flu."
    path, kw = calls["init"]
    assert path == str(tmp_path) and kw.get("local_files_only") is True
    assert (kw.get("device"), kw.get("compute_type"), kw.get("cpu_threads")) == ("cpu", "int8", 2)
    audio, kw = calls["transcribe"]
    assert isinstance(audio, np.ndarray) and audio.dtype == np.float32  # never a file path (F-0018)
    assert (kw.get("language"), kw.get("beam_size")) == ("en", 1)
    fw.transcribe(np.zeros(16, np.float32))
    assert calls["init"][0] == str(tmp_path)  # lazy, loaded once


def test_transcribe_bytes_falls_back():
    class Boom:
        def transcribe(self, audio):
            raise RuntimeError("engine down")

    assert stt.transcribe_bytes(stt.Stub("ok"), FIXTURE.read_bytes()) == ("ok", "")
    text, note = stt.transcribe_bytes(Boom(), FIXTURE.read_bytes())
    assert text == "" and "please type your notes" in note and "RuntimeError" in note
    text, note = stt.transcribe_bytes(stt.Stub("ok"), _wav(rate=44100))  # bad audio also falls back
    assert text == "" and "please type your notes" in note
