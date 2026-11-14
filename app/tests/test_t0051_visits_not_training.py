"""T-0051 visits never training or gen input: refuse_training_input refuses the visit DB, backups and visit files even
under an allowed training dir; gen/ names none of them; a planted reference is flagged; the DB is gitignored.
Mutation: trainguard_visits."""
import subprocess

import pytest

from brief import config, train_guard
from brief.train_guard import TrainingInputRefused


@pytest.mark.parametrize("p", ["data/visits.db", "data/train/visits.db", "data/train/backup-20261118.sqlite",
                               "data/synthetic/x.sqlite3", "data/train/lb-visit-file-demo.json"])
def test_refuses_visit_records(p):
    with pytest.raises(TrainingInputRefused):
        train_guard.refuse_training_input(p)


def test_gen_clean_and_planted_flagged(tmp_path):
    assert train_guard.scan_for_visits(config.PROJECT / "gen") == []
    (tmp_path / "build.py").write_text('SRC = "../data/visits.db"\nT = "sf_payloads"\n')
    assert len(train_guard.scan_for_visits(tmp_path)) == 2


def test_db_gitignored():
    r = subprocess.run(["git", "check-ignore", "-q", "data/visits.db"], cwd=config.PROJECT)
    assert r.returncode == 0
    files = subprocess.run(["git", "ls-files"], cwd=config.PROJECT, capture_output=True, text=True).stdout.split()
    assert not [f for f in files if f.endswith((".db", ".sqlite", ".sqlite3"))]
