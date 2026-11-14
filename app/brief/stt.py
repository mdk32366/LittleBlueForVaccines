"""Offline speech-to-text for visit notes (v0.2-c, PR 7; AS-0047 (STT engine and model)).

Seam: get_transcriber() -> (FasterWhisper | Stub | None, reason). None hides the audio widget and the typed notes
still work. transcribe_bytes() never raises: any decode or engine error falls back to typed notes with a note.

Rules (spec §5, F-0018 (PyAV path decode fails)):
- The recording is decoded in memory with stdlib `wave` + numpy to float32 at 16 kHz; faster-whisper is handed the
  array, never a file path, so PyAV is not on the hot path.
- Raw audio is never written to disk or to the visit store (AS-0059 (raw audio is not kept)); only the transcript,
  after the rep edits it in the notes box, is saved.
- The model loads only from a local directory (local_files_only=True); nothing is downloaded at runtime.

Config (env): LB_STT = faster-whisper (default) | stub | off; LB_STT_MODEL = small.en (default) | base.en | tiny.en;
LB_STT_MODEL_DIR = that model's directory (default <repo>/models/faster-whisper-<model>, gitignored);
LB_STT_STUB_TEXT = the Stub's transcript.
"""
from __future__ import annotations

import importlib.util
import io
import os
import wave
from pathlib import Path

import numpy as np

from . import config

SAMPLE_RATE = 16000
DEFAULT_MODEL = "small.en"            # the more accurate model is the default (AS-0047 (STT engine and model))
MODELS = ("small.en", "base.en", "tiny.en")  # base.en is the swap (LB_STT_MODEL=base.en); tiny.en low-resource
ENGINE_ARGS = dict(device="cpu", compute_type="int8", cpu_threads=2)
DECODE_ARGS = dict(language="en", beam_size=1)
FALLBACK_NOTE = "Voice transcription failed ({err}); please type your notes."
STUB_TEXT = "Stub transcript: talked with the clinic manager about flu season and shingles."


class AudioError(ValueError):
    """The recording is not a 16 kHz 16-bit PCM WAV."""


def decode_wav(data: bytes) -> np.ndarray:
    """WAV bytes -> mono float32 in [-1, 1) at 16 kHz. In memory only; refuses anything else."""
    try:
        with wave.open(io.BytesIO(data), "rb") as w:
            rate, width, ch, n = w.getframerate(), w.getsampwidth(), w.getnchannels(), w.getnframes()
            frames = w.readframes(n)
    except (wave.Error, EOFError) as e:
        raise AudioError(f"not a WAV recording ({e})") from e
    if rate != SAMPLE_RATE:
        raise AudioError(f"sample rate {rate} Hz, expected {SAMPLE_RATE}")
    if width != 2:
        raise AudioError(f"{8 * width}-bit samples, expected 16-bit PCM")
    if ch < 1:
        raise AudioError("no audio channels")
    a = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
    if ch > 1:
        a = a[: len(a) - len(a) % ch].reshape(-1, ch).mean(axis=1).astype(np.float32)
    if a.size == 0:
        raise AudioError("empty recording")
    return a


class Stub:
    """Fixed transcript (tests and demos without a model)."""
    name = "stub"

    def __init__(self, text: str = STUB_TEXT):
        self.text = text

    def transcribe(self, audio: np.ndarray) -> str:
        return self.text


class FasterWhisper:
    """faster-whisper on CPU, int8, 2 threads, beam 1, English. The model loads lazily on first use."""

    def __init__(self, model: str, model_dir: Path):
        self.name = f"faster-whisper {model}"
        self.model, self.model_dir, self._m = model, Path(model_dir), None

    def _engine(self):
        if self._m is None:
            from faster_whisper import WhisperModel  # optional dependency (app/requirements-voice.txt)
            self._m = WhisperModel(str(self.model_dir), local_files_only=True, **ENGINE_ARGS)
        return self._m

    def transcribe(self, audio: np.ndarray) -> str:
        segs, _info = self._engine().transcribe(audio, **DECODE_ARGS)
        return " ".join(s.text.strip() for s in segs).strip()


def model_name() -> str:
    return os.environ.get("LB_STT_MODEL") or DEFAULT_MODEL


def model_dir(model: str | None = None) -> Path:
    env = os.environ.get("LB_STT_MODEL_DIR")
    return Path(env) if env else config.PROJECT / "models" / f"faster-whisper-{model or model_name()}"


def config_key() -> tuple:
    """Everything get_transcriber() reads, so a cache keyed on it rebuilds when the config changes."""
    return tuple(os.environ.get(k, "") for k in ("LB_STT", "LB_STT_MODEL", "LB_STT_MODEL_DIR", "LB_STT_STUB_TEXT"))


def get_transcriber():
    """-> (transcriber, "") or (None, reason). Cheap: checks config and files; the model loads on first use."""
    mode = (os.environ.get("LB_STT") or "faster-whisper").strip().lower()
    if mode == "off":
        return None, "turned off (LB_STT=off)"
    if mode == "stub":
        return Stub(os.environ.get("LB_STT_STUB_TEXT") or STUB_TEXT), ""
    if mode != "faster-whisper":
        return None, f"unknown LB_STT value {mode!r}"
    model = model_name()
    if model not in MODELS:
        return None, f"unknown model {model!r} (LB_STT_MODEL)"
    if importlib.util.find_spec("faster_whisper") is None:
        return None, "faster-whisper is not installed"
    d = model_dir(model)
    if not (d / "model.bin").is_file():
        return None, f"model {model} not found in the local model directory"
    return FasterWhisper(model, d), ""


def transcribe_bytes(transcriber, data: bytes) -> tuple[str, str]:
    """-> (transcript, "") or ("", note). Never raises; any failure falls back to typed notes."""
    try:
        return transcriber.transcribe(decode_wav(data)), ""
    except Exception as e:  # engine, model or decode trouble never blocks a visit record
        return "", FALLBACK_NOTE.format(err=type(e).__name__)
