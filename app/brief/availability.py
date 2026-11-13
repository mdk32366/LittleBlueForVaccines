"""availability.py: the single registry of what the client's v0.2 asks can and cannot be computed from the data.

REGISTRY maps "<item>.<level>" (level = system | state | national) to Entry(status, reason, columns). The UI, the
payload and the tests all read it. Status is one of:
- OK: the column exists and the metric is computed as asked.
- DERIVED: computed through a stated mapping or heuristic; the reason is the caveat and is shown with the value.
- NOT AVAILABLE: no column supports it; it renders the literal text "not available: <reason>" and never a number.
`gate()` is the only way client_metrics reaches a computation, so a NOT AVAILABLE metric is never computed.
Reasons carry no digits (they are rendered next to numbers and through the digit rule of validator.py).
Field mapping: AS-0042 (client field mapping). Comparators: AS-0043 (comparators). Ratio rule: AS-0044 (ratio rule)."""
from __future__ import annotations

from dataclasses import dataclass

OK, DERIVED, NA = "OK", "DERIVED", "NOT AVAILABLE"
LEVELS = ("system", "state", "national")


@dataclass(frozen=True)
class Entry:
    status: str
    reason: str
    columns: tuple = ()


@dataclass(frozen=True)
class NotAvailable:
    reason: str


# The client's asks (spec §3, updated by the client email 2026-11-13): key system attributes A1-A11, important ratios
# R1-R7 (R4 the client's interim definition) and the two OBGYN ratios over Tdap, and the other items (system grouping, real system universe, highest dollars).
ITEMS = {
    "A1": "Total System Vaccines Dollars",
    "A1M": "In-state peer median dollars (scale for A1)",
    "A2": "% Vaccines Dollars by Class",
    "A3": "% Vaccines Dollars by Specialty",
    "A4": "% Vaccines Doses by Class and Specialty",
    "A5": "Corporate_Parent_Type",
    "A6": "Corporate_Parent_State",
    "A7": "# of Subsidiary",
    "A8": "# of DDD_Number",
    "A9": "# of DDD_Number by Specialty",
    "A10": "Public vs. Private babies (estimate)",
    "A11": "Pediatric vs. Adult",
    "R1": "MenB + MenABCWY to MenACWY + MenABCWY",
    "R2": "HPV to MenACWY + MenABCWY",
    "R3": "Influenza to COVID Vaccine",
    "R4": "HepB Ped to DTaP (the client's interim definition)",
    "R5": "Shingles to adult-labelled Influenza",
    "R6": "RSV Vaccine to adult-labelled Influenza",
    "R7": "Women's Health: Boostrix, Influenza and RSV Vaccine doses in season",
    "R7_FLU_TDAP": "Women's Health in season: Influenza to Tdap",
    "R7_RSV_TDAP": "Women's Health in season: RSV Vaccine to Tdap",
    "SYSKEY": "Grouped by BAC_CORP_PAR_IMS_ORG_ID",
    "UNIVERSE": "The entire universe of systems",
    "HD": "Highest dollars by class, specialty and manufacturer",
}

_NO_NAT_ID = "the national file has no system, state or outlet columns; it is pooled only"
_LABEL = "a label attribute; there is no peer value to compare"
_R4 = ("the client's interim definition: subclass HepB with Ped label over class DTaP; synthetic HepB Ped doses are "
       "zero in every system, so the synthetic value is zero, not an estimate")
_AGE = "Age_Group maps to VAC_AGE_GRP_NM, a product label and not patient age"
_BABIES = ("the client's heuristic: total = Varicella doses / two, private = DTaP doses / five, public = total - private; "
           "an estimate, inconsistent when private exceeds total")
_R7 = ("OBGYN maps to the Women's Health specialty; the season is the Oct-Mar month window of the latest full season; "
       "SEASON_DESC is not used")


def _all(status, reason, cols=()):
    return {lvl: Entry(status, reason, cols) for lvl in LEVELS}


def _build() -> dict:
    spec = {
        "A1": {"system": Entry(OK, "sum of DOLLARS", ("DOLLARS",)),
               "state": Entry(OK, "the system's share of the state total including the system, bounded zero to one",
                              ("DOLLARS", "BAC_CORP_PAR_ST_CD")),
               "national": Entry(OK, "the system's share of national dollars", ("DOLLARS",))},
        "A1M": {"system": Entry(OK, "the system's own dollars", ("DOLLARS",)),
                "state": Entry(OK, "median of the in-state peers' dollars, for scale", ("DOLLARS", "BAC_CORP_PAR_ST_CD")),
                "national": Entry(NA, "the national file has no system id, so there is no per-system median")},
        "A2": _all(OK, "DOLLARS by VAC_PROD_CLAS_NM over all DOLLARS", ("VAC_PROD_CLAS_NM", "DOLLARS")),
        "A3": _all(OK, "DOLLARS by BAC_CHNL_SPEC_DESC over all DOLLARS", ("BAC_CHNL_SPEC_DESC", "DOLLARS")),
        "A4": _all(OK, "DOSES by class and specialty over all DOSES",
                   ("VAC_PROD_CLAS_NM", "BAC_CHNL_SPEC_DESC", "DOSES")),
        "A5": {"system": Entry(OK, "BAC_CORP_PAR_ORG_TYP_DESC, one value per system", ("BAC_CORP_PAR_ORG_TYP_DESC",)),
               "state": Entry(NA, _LABEL),
               "national": Entry(DERIVED, "national dollars split by the same parent type (a type-peer mix)",
                                 ("BAC_CORP_PAR_ORG_TYP_DESC", "DOLLARS"))},
        "A6": {"system": Entry(OK, "BAC_CORP_PAR_ST_CD, one value per system", ("BAC_CORP_PAR_ST_CD",)),
               "state": Entry(NA, _LABEL),
               "national": Entry(NA, "the national file has no state column")},
        "A7": {"system": Entry(DERIVED, "distinct non-blank BAC_OWN_SUBS_IMS_ORG_ID; a synthetic artefact, "
                                        "subsidiary ids are shared across parents", ("BAC_OWN_SUBS_IMS_ORG_ID",)),
               "state": Entry(DERIVED, "median over in-state peers; a synthetic artefact, subsidiary ids are shared "
                                       "across parents", ("BAC_OWN_SUBS_IMS_ORG_ID",)),
               "national": Entry(NA, "the national file has no subsidiary column")},
        "A8": {"system": Entry(OK, "distinct DDD_OTLT_NBR", ("DDD_OTLT_NBR",)),
               "state": Entry(OK, "median over in-state peers of distinct DDD_OTLT_NBR", ("DDD_OTLT_NBR",)),
               "national": Entry(NA, "the national file has no outlet column")},
        "A9": {"system": Entry(DERIVED, "distinct DDD_OTLT_NBR with a row in that specialty; specialty is per row, "
                                        "not per outlet, so the counts add up to more than the outlet count",
                               ("DDD_OTLT_NBR", "BAC_CHNL_SPEC_DESC")),
               "state": Entry(DERIVED, "median over in-state peers; specialty is per row, not per outlet",
                              ("DDD_OTLT_NBR", "BAC_CHNL_SPEC_DESC")),
               "national": Entry(NA, "the national file has no outlet column")},
        "A10": _all(DERIVED, _BABIES, ("VAC_PROD_CLAS_NM", "DOSES")),
        "A11": _all(DERIVED, _AGE + "; shares of all doses", ("VAC_AGE_GRP_NM", "DOSES")),
        "R1": _all(OK, "subclass MenB or MenABCWY over subclass MenACWY or MenABCWY", ("VAC_PROD_SUBCLAS_NM", "DOSES")),
        "R2": _all(OK, "class HPV over subclass MenACWY or MenABCWY",
                   ("VAC_PROD_CLAS_NM", "VAC_PROD_SUBCLAS_NM", "DOSES")),
        "R3": _all(OK, "class Influenza over subclass COVID Vaccine (antivirals excluded by subclass)",
                   ("VAC_PROD_CLAS_NM", "VAC_PROD_SUBCLAS_NM", "DOSES")),
        "R4": _all(DERIVED, _R4, ("VAC_PROD_SUBCLAS_NM", "VAC_AGE_GRP_NM", "VAC_PROD_CLAS_NM", "DOSES")),
        "R5": _all(DERIVED, "class Shingles over class Influenza with adult label; " + _AGE,
                   ("VAC_PROD_CLAS_NM", "VAC_AGE_GRP_NM", "DOSES")),
        "R6": _all(DERIVED, "the full RSV Vaccine subclass, every product, over class Influenza with adult label; "
                            "the older-adult proxy is dropped; " + _AGE,
                   ("VAC_PROD_SUBCLAS_NM", "VAC_PROD_CLAS_NM", "VAC_AGE_GRP_NM", "DOSES")),
        "R7": _all(DERIVED, _R7 + "; shown as three shares of their sum",
                   ("BAC_CHNL_SPEC_DESC", "PROD_NM", "VAC_PROD_CLAS_NM", "VAC_PROD_SUBCLAS_NM", "MTH_ID", "DOSES")),
        "R7_FLU_TDAP": _all(DERIVED, _R7 + "; class Influenza over subclass Tdap",
                            ("BAC_CHNL_SPEC_DESC", "VAC_PROD_CLAS_NM", "VAC_PROD_SUBCLAS_NM", "MTH_ID", "DOSES")),
        "R7_RSV_TDAP": _all(DERIVED, _R7 + "; subclass RSV Vaccine over subclass Tdap",
                            ("BAC_CHNL_SPEC_DESC", "VAC_PROD_SUBCLAS_NM", "MTH_ID", "DOSES")),
        "SYSKEY": {"system": Entry(OK, "synthetic systems keyed by BAC_CORP_PAR_IMS_ORG_ID",
                                   ("BAC_CORP_PAR_IMS_ORG_ID",)),
                   "state": Entry(OK, "synthetic in-state peers keyed by BAC_CORP_PAR_IMS_ORG_ID",
                                  ("BAC_CORP_PAR_IMS_ORG_ID", "BAC_CORP_PAR_ST_CD")),
                   "national": Entry(NA, "the national file has no system id; " + _NO_NAT_ID)},
        "UNIVERSE": {"system": Entry(OK, "every synthetic system is loaded", ("BAC_CORP_PAR_IMS_ORG_ID",)),
                     "state": Entry(OK, "every synthetic system is loaded", ("BAC_CORP_PAR_IMS_ORG_ID",)),
                     "national": Entry(NA, "there is no real system-level file; " + _NO_NAT_ID)},
        "HD": _all(OK, "DOLLARS ranked by class, specialty and manufacturer, with the comparator share per item",
                   ("VAC_PROD_CLAS_NM", "BAC_CHNL_SPEC_DESC", "MFR_NM", "DOLLARS")),
    }
    return {f"{item}.{lvl}": e for item, levels in spec.items() for lvl, e in levels.items()}


REGISTRY = _build()


def entry(key: str) -> Entry:
    return REGISTRY[key]


def status(key: str) -> str:
    return REGISTRY[key].status


def gate(key: str, compute):
    """Run compute() only when the metric is available; a NOT AVAILABLE metric returns NotAvailable, never a number."""
    e = REGISTRY[key]
    if e.status == NA:
        return NotAvailable(e.reason)
    return compute()


def render_na(key: str) -> str:
    return f"not available: {REGISTRY[key].reason}"


def status_text(key: str) -> str:
    e = REGISTRY[key]
    if e.status == NA:
        return render_na(key)
    if e.status == DERIVED:
        return f"derived: {e.reason}"
    return "ok"
