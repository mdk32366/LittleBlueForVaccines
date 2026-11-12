"""Paths and constants. LLM is OFF in this build: there is no LLM client code at all."""
import os
from pathlib import Path

APP_NAME = "Little Blue for Vaccine Sales"  # D-0033 (name), Matt 12:19 PT 2026-11-12
PROJECT = Path(__file__).resolve().parents[2]  # repository root
SALES_FILE = "BIA_562_Synthetic_Sales_Data.csv"


def _default_data(name: str) -> Path:
    """<repo>/data/<name> (repository layout), else <repo>/<name> (legacy local fallback)."""
    repo_data = PROJECT / "data" / name
    return repo_data if repo_data.exists() else PROJECT / name


DATA_PATH = Path(os.environ.get("DATA_PATH") or _default_data(SALES_FILE))
GEN_OUT = Path(os.environ.get("GEN_OUT", PROJECT / "gen" / "out"))
BENCHMARK = "synthetic"            # §0 item 1: pluggable; default synthetic peers. "national" per D-0034 (benchmark.py)
BENCH_LABEL = "synthetic peers"    # Fact.source_label for benchmark-derived facts (§1, T-0008)
SYSTEM_LABEL = "system"            # Fact.source_label for system-only facts (see AS-0030)
LLM_MODE = "off"                   # brief + D-0022 (fake data) order: LLM off everywhere; narrative is templated
AS_OF = "202609"                   # data's last month (program-level as-of-month assumption)
AS_OF_DATE = "2026-09-30"          # last day of AS_OF; a contract that ended before this is shown as expired
FULL_PERIOD = ("202410", "202609")
W1 = ("202410", "202503")          # §0 item 3 switching windows (program-level window assumption)
W2 = ("202604", "202609")
T12 = ("202510", "202609")         # F7 trailing 12
P12 = ("202410", "202509")         # F7 prior 12
