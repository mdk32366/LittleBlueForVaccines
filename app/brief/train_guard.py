"""T-0025 guard, app side: the national file (D-0034 (national file public-real)) is NOT training or generator input.
`refuse_training_input` is the check the future train/build_dataset path must call; `scan_for_national` audits a code /
output tree (used on gen/, read-only) for any reference to or consumption of the national file."""
import json
from pathlib import Path

from .benchmark import NATIONAL_FILE

ALLOWED_TRAIN_DIRS = ("data/synthetic/", "data/train/")  # §9.5 T-0025


class TrainingInputRefused(ValueError):
    pass


def refuse_training_input(path, national_sha256: str | None = None) -> None:
    p = Path(path)
    s = p.as_posix()
    if NATIONAL_FILE in s or "National System Data" in s:
        raise TrainingInputRefused(f"T-0025: national file is not training input: {p}")
    if not any(d in s for d in ALLOWED_TRAIN_DIRS):
        raise TrainingInputRefused(f"T-0025: training input must be under {ALLOWED_TRAIN_DIRS}: {p}")
    if national_sha256 and p.exists():
        import hashlib
        if hashlib.sha256(p.read_bytes()).hexdigest() == national_sha256:
            raise TrainingInputRefused(f"T-0025: {p} is a copy of the national file")


def refuse_record(rec: dict) -> None:
    if rec.get("synthetic") is not True:
        raise TrainingInputRefused("T-0025: record without synthetic: true")


def scan_for_national(root, national_sha256: str | None = None) -> list:
    """Violations: any .py/.json/.jsonl/.md/.txt/.toml/.cfg file under root naming the national file, or a manifest
    whose systems_source is the national file (by name or sha256)."""
    bad = []
    root = Path(root)
    for p in sorted(root.rglob("*")):
        if not p.is_file() or ".venv" in p.parts or "__pycache__" in p.parts:
            continue
        if p.suffix not in (".py", ".json", ".jsonl", ".md", ".txt", ".toml", ".cfg", ".sh"):
            continue
        if p.suffix == ".md" and "docs" in p.parts:
            continue  # living docs may discuss the file; code and outputs may not consume it
        t = p.read_text(errors="replace")
        if NATIONAL_FILE in t or "National System Data" in t:
            bad.append(f"{p}: names the national file")
        if p.name == "manifest.json":
            src = (json.loads(t).get("systems_source") or {})
            if NATIONAL_FILE in str(src.get("file", "")) or (national_sha256 and src.get("sha256") == national_sha256):
                bad.append(f"{p}: systems_source is the national file")
    return bad
