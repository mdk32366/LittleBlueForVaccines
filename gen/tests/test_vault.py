"""T-0027 vault contamination (ONTOLOGY §5): each of the four cases must trip. Uses tmp paths only."""
import pytest

from bia562gen import leaves, vault_guard
from bia562gen.generate import generate
from bia562gen.vault_guard import PROVENANCE_MARKERS, VAULT_PATH_MARKERS, VaultContamination

GOOD_ID = "CL-SYN-SYNCP000001-MSA1-4.2"
# Vault-path and provenance literals come only from the denylist constants in vault_guard.py.
MARKER0 = VAULT_PATH_MARKERS[0]


def test_v1_leaf_at_grok_bot_path_rejected(tmp_path):
    with pytest.raises(VaultContamination, match="V1"):
        leaves.guard(tmp_path / MARKER0 / "leaves" / f"{GOOD_ID}.md", GOOD_ID, "body")
    for marker in VAULT_PATH_MARKERS[1:]:
        with pytest.raises(VaultContamination, match="V1"):
            vault_guard.check_path(tmp_path / marker / "x.md")


def test_v1_generator_refuses_vault_out_root(tmp_path, spec, systems):
    with pytest.raises(VaultContamination, match="V1"):
        generate(spec, systems, tmp_path / MARKER0 / "out", 562)
    assert not (tmp_path / MARKER0).exists()


def test_v2_vault_shaped_id_rejected(tmp_path):
    for bad in ("D-0001", "AS-0004", "T-0027", "F-0001", "random-note"):
        with pytest.raises(VaultContamination, match="V2"):
            leaves.guard(tmp_path / f"{bad}.md", bad, "body")


def test_v3_provenance_marker_rejected(tmp_path):
    with pytest.raises(VaultContamination, match="V3"):
        leaves.guard(tmp_path / f"{GOOD_ID}.md", GOOD_ID, f"text\n{PROVENANCE_MARKERS[0]} decisions.md L1-2 -->\n")
    with pytest.raises(VaultContamination, match="V3"):
        leaves.guard(tmp_path / f"{GOOD_ID}.md", GOOD_ID, f"{PROVENANCE_MARKERS[1]} x -->")


def test_v4_md_in_vendored_code_dir_rejected(tmp_path):
    d = tmp_path / "src" / "brief" / "leafstore"
    d.mkdir(parents=True)
    (d / "leafstore_index.py").write_text("# code\n")
    vault_guard.check_vendored_dir(d)  # .py only: ok
    (d / "D-0001.md").write_text("leaf\n")
    with pytest.raises(VaultContamination, match="V4"):
        vault_guard.check_vendored_dir(d)


def test_clean_leaf_passes(tmp_path):
    assert leaves.guard(tmp_path / f"{GOOD_ID}.md", GOOD_ID, "clean body")
