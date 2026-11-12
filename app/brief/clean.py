"""clean.py (§1 clean rules): returns are netted into totals; a null class becomes "Unclassified"."""
import pandas as pd


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for c in ("VAC_PROD_CLAS_NM", "VAC_PROD_SUBCLAS_NM", "MFR_NM", "BAC_CHNL_SPEC_DESC"):
        df[c] = df[c].where(df[c].str.strip() != "", "Unclassified")
    df["IS_RETURN"] = df["DOLLARS"] < 0
    return df
