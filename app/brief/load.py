"""load.py: schema check (fails closed on a missing column), types; input hash check against gen's manifest."""
import hashlib
import json
from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS = [
    "MTH_ID", "PROD_NM", "MFR_NM", "VAC_PROD_CLAS_NM", "VAC_PROD_SUBCLAS_NM", "VAC_AGE_GRP_NM", "VAC_FRZ_IND",
    "SEASON_DESC", "BAC_CHNL_SPEC_DESC", "BAC_IMS_ORG_ID", "DDD_OTLT_NBR", "DDD_SUBCAT", "DDD_OUTLET_NAME",
    "DDD_OUTLET_ADDRESS", "DDD_OUTLET_CITY", "DDD_OUTLET_STATE", "BAC_CORP_PAR_IMS_ORG_ID", "BAC_CORP_PAR_NM",
    "BAC_OWN_SUBS_IMS_ORG_ID", "BAC_OWN_SUBS_NM", "BAC_CORP_PAR_ORG_TYP_DESC", "BAC_CORP_PAR_ST_CD", "DOSES", "DOLLARS",
]
STR_COLS = [c for c in REQUIRED_COLUMNS if c not in ("DOSES", "DOLLARS")]


class SchemaError(ValueError):
    pass


def check_schema(df: pd.DataFrame) -> None:
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise SchemaError(f"missing required columns: {missing}")


def load_csv(path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={c: str for c in STR_COLS}, keep_default_na=False, encoding="utf-8-sig")
    check_schema(df)
    df["DOSES"] = pd.to_numeric(df["DOSES"], errors="raise").astype("int64")
    df["DOLLARS"] = pd.to_numeric(df["DOLLARS"], errors="raise").astype("float64")
    return df


def sha256_file(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def gen_manifest_input_sha(gen_out) -> str | None:
    p = Path(gen_out) / "manifest.json"
    if not p.exists():
        return None
    return (json.loads(p.read_text()).get("systems_source") or {}).get("sha256")
