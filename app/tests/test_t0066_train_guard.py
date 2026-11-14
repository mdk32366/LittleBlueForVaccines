"""T-0066 (supersedes T-0025 for gen, D-0042 (T-0025 retired for gen)): the training-input guard under D-0041 (national
file is generator and training input). The national file is accepted only by its recorded sha256; visit records and DBs
(T-0051) and any other non-synthetic file are still refused. Mutations: trainguard, guard_open."""
import json

import pytest

from brief import benchmark as bm, config, load, train_guard
from brief.train_guard import TrainingInputRefused


def test_recorded_sha_is_the_national_file():
    assert load.sha256_file(bm.national_path()) == train_guard.NATIONAL_SHA256


def test_accepts_national_only_by_recorded_sha(tmp_path):
    train_guard.refuse_training_input(bm.national_path())  # the recorded file: accepted
    cp = tmp_path / "elsewhere" / "copy.csv"
    cp.parent.mkdir()
    cp.write_bytes(bm.national_path().read_bytes())
    train_guard.refuse_training_input(cp)  # same bytes at another path: accepted by sha
    bad = tmp_path / bm.NATIONAL_FILE
    bad.write_bytes(bm.national_path().read_bytes() + b"\n")
    with pytest.raises(TrainingInputRefused, match="sha256 differs"):
        train_guard.refuse_training_input(bad)
    with pytest.raises(TrainingInputRefused, match="missing"):
        train_guard.refuse_training_input(tmp_path / "data" / "train" / bm.NATIONAL_FILE)


def test_still_refuses_visits_and_other_files(tmp_path):
    for p in ("data/train/visits.db", "data/train/backup.sqlite3", "data/train/lb-visit-file-1.json"):
        with pytest.raises(TrainingInputRefused, match="T-0051"):
            train_guard.refuse_training_input(p)
    with pytest.raises(TrainingInputRefused):
        train_guard.refuse_training_input("/tmp/train.jsonl")
    other = tmp_path / "other.csv"
    other.write_text("a,b\n1,2\n")
    with pytest.raises(TrainingInputRefused):
        train_guard.refuse_training_input(other)
    train_guard.refuse_training_input("data/train/train.jsonl")  # allowed


def test_refuses_non_synthetic_record():
    with pytest.raises(TrainingInputRefused):
        train_guard.refuse_record({"qa_id": "x"})
    train_guard.refuse_record({"synthetic": True})


def test_gen_names_national_only_where_allowed():
    gen = config.PROJECT / "gen"
    assert train_guard.scan_national_mentions(gen) == []
    m = json.loads((config.GEN_OUT / "manifest.json").read_text())
    assert m["systems_source"]["sha256"] != train_guard.NATIONAL_SHA256
    assert m["benchmark_source"]["sha256"] == train_guard.NATIONAL_SHA256


def test_scan_flags_planted_reference(tmp_path):
    (tmp_path / "build_dataset.py").write_text(f'SRC = "../{bm.NATIONAL_FILE}"\n')
    (tmp_path / "out").mkdir()
    (tmp_path / "out" / "manifest.json").write_text(json.dumps({
        "systems_source": {"file": "x", "sha256": train_guard.NATIONAL_SHA256},
        "benchmark_source": {"file": bm.NATIONAL_FILE, "sha256": "abc"}}))
    bad = train_guard.scan_national_mentions(tmp_path)
    assert len(bad) == 3, bad
