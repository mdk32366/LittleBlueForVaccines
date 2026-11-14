"""schema_v1 national input (D-0041 (national file is generator and training input)): the public-real national file
(D-0034 (national file public-real)) feeds the generator as POOLED totals only. Fail-closed:
- the file must exist and its sha256 must equal RECORDED_SHA256, else NationalInputError (no fallback to synthetic
  peers, ever);
- only USED_COLUMNS are read (VAC_FRZ_IND and SEASON_DESC are not);
- nothing row-level leaves this module: load() returns pooled components (profile_metrics.Acc) and the file record
  for the manifest's benchmark_source.
Pooling matches app/brief/benchmark.national_profile(): one aggregate over the FULL window, blanks read as
"Unclassified", plus the R7 Women's Health season. Parity is tested app-side (T-0064) and pinned gen-side (T-0065)."""
from __future__ import annotations

import csv
import hashlib
from pathlib import Path

from . import profile_metrics as PM

NATIONAL_FILE = "BIA 562 National System Data.csv"
RECORDED_SHA256 = "67aca8560ce9b5a08cff8a1a305154375d6dabbabfd5a9df23d84217012caeed"
USED_COLUMNS = ("MTH_ID", "PROD_NM", "MFR_NM", "VAC_PROD_CLAS_NM", "VAC_PROD_SUBCLAS_NM", "VAC_AGE_GRP_NM",
                "BAC_CHNL_SPEC_DESC", "BAC_CORP_PAR_ORG_TYP_DESC", "DOSES", "DOLLARS")
DEFAULT_PATH = Path(__file__).resolve().parents[2] / "data" / NATIONAL_FILE


class NationalInputError(RuntimeError):
    """The national file is missing, altered, or lacks a used column. The generator stops; it never falls back."""


def sha256_file(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def project(row: dict) -> dict:
    """The only view of a national row the generator sees: USED_COLUMNS, nothing else."""
    try:
        return {c: row[c] for c in USED_COLUMNS}
    except KeyError as e:
        raise NationalInputError(f"national file lacks column {e}") from None


def load(path=None, expected_sha256: str | None = RECORDED_SHA256) -> dict:
    """{"pooled": Acc.pooled() dict, "source": {file, sha256, rows}}. expected_sha256=None is for tests on a
    hand-built copy only; the generator always passes the recorded hash (schema_v1.SchemaV1Spec)."""
    p = Path(path) if path else DEFAULT_PATH
    if not p.is_file():
        raise NationalInputError(f"national file missing: {p.name}")
    sha = sha256_file(p)
    if expected_sha256 is not None and sha != expected_sha256:
        raise NationalInputError(f"national file sha256 {sha[:12]} != recorded {expected_sha256[:12]}")
    acc = PM.Acc()
    with open(p, newline="", encoding="utf-8-sig") as f:
        for raw in csv.DictReader(f):
            acc.add(PM.clean_row(project(raw)))
    return {"pooled": acc.pooled(), "source": {"file": p.name, "sha256": sha, "rows": acc.rows}}
