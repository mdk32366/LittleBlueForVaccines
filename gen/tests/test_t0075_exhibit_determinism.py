"""T-0075 (exhibit determinism): EXH1 is a pure function of the two input files: its text is identical across seeds
(the system RNG never reaches it); T-0028 manifest identity is test_determinism / test_real_out."""
from bia562gen.generate import make_rng, render_doc_md


def _exh(spec, system, seed, family):
    ds = [d for d in spec.plan(system, make_rng(f"{seed}|{spec.spec_version}|{system.system_id}"), family)
          if d.doc_type == "EXH"][0]
    return render_doc_md(spec.render(ds), {"doc_id": ds.doc_id})


def test_exhibit_identical_across_seeds(v1_spec, real_systems):
    for system in real_systems[:12]:
        for fam in ("A", "B"):
            assert _exh(v1_spec, system, 562, fam) == _exh(v1_spec, system, 563, fam), (system.system_id, fam)
