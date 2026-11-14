"""T-0046 STT in the Visit record tab (AppTest): a Stub transcript pre-fills the notes box and is saved; LB_STT=off
hides the recorder with a "voice unavailable" caption and typed notes still save; an engine exception falls back to
typed notes with a note; no audio bytes end up on disk or in the visit store (AS-0059 (raw audio is not kept)).
One recording is transcribed once, however many reruns follow; a transcript that would push the notes past the
8,000-character limit is cut to the limit with a caption, keeping the typed text first.
Mutations: stt_none, stt_nofallback, stt_persist (the recording is written next to the store), stt_prefill
(the transcript is dropped), stt_dedupe (every rerun re-transcribes), stt_cap (the transcript is not cut)."""
import datetime
import tempfile
from pathlib import Path

from streamlit.testing.v1 import AppTest

from brief import config, stt, visits

APP = str(Path(__file__).resolve().parents[1] / "app.py")
FIXTURE = Path(stt.__file__).parent / "fixtures" / "visit_note_fixture_16k.wav"
D = datetime.date(2026, 11, 18)
SPOKEN = "We talked about HPV uptake with the clinic manager."


def _app(tmp_path, monkeypatch, mode="stub"):
    monkeypatch.setenv("LB_VISITS_DB", str(tmp_path / "ui.db"))
    monkeypatch.setenv("LB_STT", mode)
    monkeypatch.setenv("LB_STT_STUB_TEXT", SPOKEN)
    at = AppTest.from_file(APP, default_timeout=240).run()
    assert not at.exception
    at.selectbox(key="system").set_value("SYNCP000025").run()
    assert not at.exception
    at.text_input(key="vr_rep").input("Voice Rep").run()
    at.date_input(key="vr_date").set_value(D).run()
    return at


def _record(at):
    at.audio_input(key="vr_audio").set_value(("note.wav", FIXTURE.read_bytes(), "audio/wav")).run()
    assert not at.exception
    return at


def _save(at, tmp_path):
    at.button(key="vr_save").click().run()
    assert not at.exception
    assert [s.value for s in at.success if s.value.startswith("Saved visit")]
    return visits.lookup("voice rep", D.isoformat(), "SYNCP000025", db=tmp_path / "ui.db")


def test_stub_prefills_notes_and_saves(tmp_path, monkeypatch):
    at = _app(tmp_path, monkeypatch)
    at.text_area(key="vr_notes").input("Typed first.").run()
    _record(at)
    assert at.text_area(key="vr_notes").value == "Typed first.\n" + SPOKEN  # appended to what was typed
    assert any("recording is not kept" in c.value for c in at.caption)
    at.text_area(key="vr_notes").input(SPOKEN + " Edited.").run()  # the rep edits; a rerun does not re-transcribe
    assert at.text_area(key="vr_notes").value == SPOKEN + " Edited."
    stored = _save(at, tmp_path)
    assert stored["visit"]["notes_text"] == SPOKEN + " Edited."
    outs = {o["key"]: o for o in stored["visit"]["outcomes"]}
    assert outs["must.R2"]["addressed"] == "Raised"  # the keyword hint works on the transcript ("HPV")


def test_none_hides_recorder_typed_still_saves(tmp_path, monkeypatch):
    at = _app(tmp_path, monkeypatch, mode="off")
    assert len(at.get("audio_input")) == 0
    assert any(c.value.startswith("voice unavailable: turned off") for c in at.caption)
    at.text_area(key="vr_notes").input("Typed only.").run()
    assert _save(at, tmp_path)["visit"]["notes_text"] == "Typed only."


def test_exception_falls_back_to_typed(tmp_path, monkeypatch):
    def boom(self, audio):
        raise RuntimeError("engine down")

    monkeypatch.setattr(stt.Stub, "transcribe", boom)
    at = _record(_app(tmp_path, monkeypatch))
    assert any("please type your notes" in w.value for w in at.warning)
    assert at.text_area(key="vr_notes").value == ""
    at.text_area(key="vr_notes").input("Typed after the failure.").run()
    assert _save(at, tmp_path)["visit"]["notes_text"] == "Typed after the failure."


def test_one_transcription_per_recording(tmp_path, monkeypatch):
    calls = []
    orig = stt.Stub.transcribe

    def counting(self, audio):
        calls.append(audio.size)
        return orig(self, audio)

    monkeypatch.setattr(stt.Stub, "transcribe", counting)
    at = _record(_app(tmp_path, monkeypatch))
    assert len(calls) == 1 and at.text_area(key="vr_notes").value == SPOKEN
    at.text_area(key="vr_notes").input("Edited by the rep.").run()
    at.text_input(key="vr_rep").input("Voice Rep 2").run()
    at.button(key="vr_save").click().run()
    assert not at.exception
    assert len(calls) == 1, f"the same recording was transcribed {len(calls)} times"
    assert at.text_area(key="vr_notes").value == "Edited by the rep."


def test_transcript_cut_to_notes_limit(tmp_path, monkeypatch):
    long_text = ("clinic manager flu shingles " * 400).strip()  # about 11,000 characters
    assert len(long_text) > visits.NOTES_MAX
    at = _app(tmp_path, monkeypatch)
    monkeypatch.setenv("LB_STT_STUB_TEXT", long_text)
    at.text_area(key="vr_notes").input("Typed first.").run()
    _record(at)
    notes = at.text_area(key="vr_notes").value
    assert len(notes) == visits.NOTES_MAX
    assert notes == ("Typed first.\n" + long_text)[: visits.NOTES_MAX]
    assert any(f"cut to the {visits.NOTES_MAX}-character notes limit" in c.value for c in at.caption)
    stored = _save(at, tmp_path)
    assert len(stored["visit"]["notes_text"]) == visits.NOTES_MAX


def _files(root: Path):
    return {p for p in root.rglob("*") if p.is_file()} if root.is_dir() else set()


def _top(root: Path):
    return {p for p in root.iterdir() if p.is_file()}


def test_no_audio_on_disk_or_in_store(tmp_path, monkeypatch):
    audio = FIXTURE.read_bytes()
    pcm = [audio[i:i + 64] for i in (4000, 60000, 200000)]  # chunks of the recording's sample data
    tmp = Path(tempfile.gettempdir())
    data_dir = config.PROJECT / "data"
    before_tmp, before_data = _top(tmp), _files(data_dir)
    at = _app(tmp_path, monkeypatch)
    _record(at)
    assert at.text_area(key="vr_notes").value == SPOKEN
    _save(at, tmp_path)
    new = _files(tmp_path) | (_top(tmp) - before_tmp) | (_files(data_dir) - before_data)
    assert any(p.name.startswith("ui.db") for p in new)  # the store itself is scanned too
    for p in new:
        try:
            blob = p.read_bytes()
        except OSError:
            continue
        assert b"WAVE" not in blob[:64] and not any(c in blob for c in pcm), f"audio bytes found in {p}"
