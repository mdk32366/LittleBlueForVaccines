"""ONTOLOGY §5 rules V1-V4 (Matt: "none of my leaves make it into this project"). T-0027 trips each."""
import re
from pathlib import Path

VAULT_PATH_MARKERS = ("Grok-Bot", "obsidian-keel", "keel-leaf-staging")  # V1
VAULT_ID_RE = re.compile(r"^(D|AS|T|F)-\d{4}$")  # V2 vault-shaped ids
PROVENANCE_MARKERS = ("<!-- keel-src", "<!-- keel:ins")  # V3


class VaultContamination(ValueError):
    pass


def check_path(path) -> None:
    """V1: any path containing a vault marker fails."""
    s = str(Path(path).resolve()) + "|" + str(path)
    for m in VAULT_PATH_MARKERS:
        if m in s:
            raise VaultContamination(f"V1: path {path} contains vault marker {m!r}")


def check_leaf_id(leaf_id: str) -> None:
    """V2: every leaf id must match a PROJECT grammar (ONTOLOGY §1); vault-shaped ids therefore fail.
    Id shapes the spec does not define are caught only by the positive project-grammar rule (see report gap list)."""
    from .ontology import match_class
    if VAULT_ID_RE.match(leaf_id):
        raise VaultContamination(f"V2: vault-shaped leaf id {leaf_id!r}")
    if match_class(leaf_id) is None:
        raise VaultContamination(f"V2: leaf id {leaf_id!r} matches no project grammar")


def check_body(leaf_id: str, text: str) -> None:
    """V3: no vault provenance markers in any leaf body or index row."""
    for m in PROVENANCE_MARKERS:
        if m in text:
            raise VaultContamination(f"V3: leaf {leaf_id} carries vault provenance marker {m!r}")


def check_vendored_dir(code_dir) -> None:
    """V4: the vendored leafstore code dir ships only .py files (no leaves/fixtures)."""
    d = Path(code_dir)
    if not d.exists():
        return
    for p in sorted(d.rglob("*")):
        if p.is_file() and p.suffix != ".py" and "__pycache__" not in p.parts:
            raise VaultContamination(f"V4: non-.py file {p} in vendored code dir {d}")


def check_leaf(path, leaf_id: str, text: str) -> None:
    check_path(path)
    check_leaf_id(leaf_id)
    check_body(leaf_id, text)
