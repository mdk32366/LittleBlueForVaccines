"""T-0066 guard (supersedes T-0025, retired for gen by D-0042 (T-0025 retired for gen)), app side.

D-0041 (national file is generator and training input): the national file now feeds the generator and may be training
input, but ONLY the exact recorded file (by sha256). `refuse_training_input` is the check the future train/build_dataset
path must call: it accepts the national file only when its bytes hash to NATIONAL_SHA256, and still refuses visit
records and DBs (T-0051) and any other file outside the synthetic training dirs. `scan_national_mentions` audits gen/
(read-only): the national file may be named only by gen/bia562gen/national.py and by the manifest's benchmark_source,
never as systems_source."""
import hashlib
import json
from pathlib import Path

from .benchmark import NATIONAL_FILE

NATIONAL_SHA256 = "67aca8560ce9b5a08cff8a1a305154375d6dabbabfd5a9df23d84217012caeed"  # same pin as gen national.py
ALLOWED_TRAIN_DIRS = ("data/synthetic/", "data/train/")  # §9.5
VISIT_SUFFIXES = (".db", ".sqlite", ".sqlite3")  # T-0051: the visit store and its backups are never training input
VISIT_MARKERS = ("visits.db", "sf_payloads", "lb-visit-file")
NATIONAL_ALLOWED = ("bia562gen/national.py",)  # gen code that may name the national file (T-0066)


class TrainingInputRefused(ValueError):
    pass


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def refuse_training_input(path, national_sha256: str = NATIONAL_SHA256) -> None:
    p = Path(path)
    s = p.as_posix()
    if p.suffix.lower() in VISIT_SUFFIXES or any(m in s for m in VISIT_MARKERS):
        raise TrainingInputRefused(f"T-0051: visit records are not training input: {p}")
    names_national = NATIONAL_FILE in s or "National System Data" in s
    if names_national or (p.is_file() and p.suffix.lower() == ".csv"):
        if not p.is_file():
            if names_national:
                raise TrainingInputRefused(f"T-0066: national file missing, cannot verify its sha256: {p}")
        elif _sha(p) == national_sha256:
            return  # D-0041: the recorded national file, by its sha256, wherever it sits
        elif names_national:
            raise TrainingInputRefused(f"T-0066: {p} is named as the national file but its sha256 differs")
    if not any(d in s for d in ALLOWED_TRAIN_DIRS):
        raise TrainingInputRefused(f"T-0066: training input must be the recorded national file or under "
                                   f"{ALLOWED_TRAIN_DIRS}: {p}")


def refuse_record(rec: dict) -> None:
    if rec.get("synthetic") is not True:
        raise TrainingInputRefused("T-0066: record without synthetic: true")


def scan_national_mentions(root, national_sha256: str = NATIONAL_SHA256) -> list:
    """Violations under root (gen/): a .py/.json/.jsonl/.md/.txt/.toml/.cfg/.sh file naming the national file other than
    bia562gen/national.py and out*/manifest.json; a manifest naming it outside benchmark_source; a manifest whose
    systems_source is the national file (by name or sha256); a benchmark_source whose sha256 is not the recorded one."""
    bad = []
    root = Path(root)
    for p in sorted(root.rglob("*")):
        if not p.is_file() or ".venv" in p.parts or "__pycache__" in p.parts:
            continue
        if p.suffix not in (".py", ".json", ".jsonl", ".md", ".txt", ".toml", ".cfg", ".sh"):
            continue
        rel = p.relative_to(root).as_posix()
        t = p.read_text(errors="replace")
        named = NATIONAL_FILE in t or "National System Data" in t
        if p.name == "manifest.json":
            m = json.loads(t)
            src = m.get("systems_source") or {}
            if NATIONAL_FILE in json.dumps(src) or src.get("sha256") == national_sha256:
                bad.append(f"{p}: systems_source is the national file")
            rest = {k: v for k, v in m.items() if k != "benchmark_source"}
            if NATIONAL_FILE in json.dumps(rest) or "National System Data" in json.dumps(rest):
                bad.append(f"{p}: names the national file outside benchmark_source")
            b = m.get("benchmark_source")
            if b is not None and b.get("sha256") != national_sha256:
                bad.append(f"{p}: benchmark_source sha256 is not the recorded national file")
            continue
        if named and not any(rel.endswith(a) for a in NATIONAL_ALLOWED):
            bad.append(f"{p}: names the national file")
    return bad


def scan_for_visits(root) -> list:
    """T-0051: code or outputs under root (gen/) that name the visit store, its payload table or a visit file."""
    bad = []
    for p in sorted(Path(root).rglob("*")):
        if not p.is_file() or ".venv" in p.parts or "__pycache__" in p.parts or p.suffix not in (
                ".py", ".json", ".jsonl", ".txt", ".toml", ".cfg", ".sh"):
            continue
        t = p.read_text(errors="replace")
        bad += [f"{p}: names {m}" for m in VISIT_MARKERS if m in t]
    return bad
