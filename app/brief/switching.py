"""F5 switching (§0 item 3): two-proportion z-test on dose share between windows W1 and W2.
Flag when both windows' class volume >= 200 doses, |share move| >= 15 points and |z| >= 3; keep the top 2 per system by |z|."""
import math

import pandas as pd

from . import config

MIN_CLASS_DOSES = 200
MIN_MOVE = 0.15
MIN_Z = 3.0
MAX_FLAGS = 2


def window_doses(df: pd.DataFrame) -> pd.DataFrame:
    m = df["MTH_ID"]
    w = pd.Series(pd.NA, index=df.index, dtype="object")
    w[(m >= config.W1[0]) & (m <= config.W1[1])] = "w1"
    w[(m >= config.W2[0]) & (m <= config.W2[1])] = "w2"
    d = df.assign(W=w).dropna(subset=["W"])
    return d.groupby(["BAC_CORP_PAR_IMS_ORG_ID", "VAC_PROD_CLAS_NM", "MFR_NM", "W"])["DOSES"].sum().unstack("W", fill_value=0)


def z_two_prop(x1, n1, x2, n2):
    p1, p2 = x1 / n1, x2 / n2
    p = (x1 + x2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2)) if 0 < p < 1 else 0.0
    return p1, p2, ((p2 - p1) / se if se > 0 else 0.0)


def flags_all(df: pd.DataFrame) -> dict:
    """system_id -> list of flags (dicts), at most MAX_FLAGS, ranked by |z|."""
    wd = window_doses(df)
    for c in ("w1", "w2"):
        if c not in wd.columns:
            wd[c] = 0
    wd = wd.clip(lower=0)  # net returns can push a manufacturer-window below zero; share is floored at 0
    cls = wd.groupby(level=[0, 1])[["w1", "w2"]].sum()
    out = {}
    for (sid, c, mfr), row in wd.iterrows():
        n1, n2 = cls.loc[(sid, c), "w1"], cls.loc[(sid, c), "w2"]
        if n1 < MIN_CLASS_DOSES or n2 < MIN_CLASS_DOSES:
            continue
        p1, p2, z = z_two_prop(row["w1"], n1, row["w2"], n2)
        if abs(p2 - p1) >= MIN_MOVE and abs(z) >= MIN_Z:
            out.setdefault(sid, []).append({"class": c, "mfr": mfr, "share_w1": p1 * 100, "share_w2": p2 * 100,
                                            "z": z, "n_w1": int(n1), "n_w2": int(n2)})
    for sid in out:
        out[sid] = sorted(out[sid], key=lambda f: (-abs(f["z"]), f["class"], f["mfr"]))[:MAX_FLAGS]
    return out
