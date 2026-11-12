"""T-0025 (app slice): the national file is never training or generator input (D-0034 (national file public-real))."""
import json

import pytest

from brief import benchmark as bm, config, load, train_guard
from brief.train_guard import TrainingInputRefused


def test_refuses_national_path():
    with pytest.raises(TrainingInputRefused):
        train_guard.refuse_training_input(bm.national_path())
    with pytest.raises(TrainingInputRefused):
        train_guard.refuse_training_input("data/train/" + bm.NATIONAL_FILE)


def test_refuses_outside_train_dirs_and_copies(tmp_path):
    with pytest.raises(TrainingInputRefused):
        train_guard.refuse_training_input("/tmp/train.jsonl")
    nat = bm.national_path()
    cp = tmp_path / "data" / "train" / "x.csv"
    cp.parent.mkdir(parents=True)
    cp.write_bytes(nat.read_bytes())
    with pytest.raises(TrainingInputRefused):
        train_guard.refuse_training_input(cp, load.sha256_file(nat))
    train_guard.refuse_training_input("data/train/train.jsonl")  # allowed


def test_refuses_non_synthetic_record():
    with pytest.raises(TrainingInputRefused):
        train_guard.refuse_record({"qa_id": "x"})
    train_guard.refuse_record({"synthetic": True})


def test_gen_does_not_consume_national():
    nat_sha = load.sha256_file(bm.national_path())
    gen = config.PROJECT / "gen"
    assert train_guard.scan_for_national(gen, nat_sha) == []
    m = json.loads((config.GEN_OUT / "manifest.json").read_text())
    assert m["systems_source"]["sha256"] != nat_sha


def test_scan_flags_planted_reference(tmp_path):
    (tmp_path / "build_dataset.py").write_text(f'SRC = "../{bm.NATIONAL_FILE}"\n')
    (tmp_path / "out").mkdir()
    (tmp_path / "out" / "manifest.json").write_text(json.dumps({"systems_source": {"file": "x", "sha256": "abc"}}))
    bad = train_guard.scan_for_national(tmp_path, "abc")
    assert len(bad) == 2
