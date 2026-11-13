"""T-0041 (auto_renew bool schema guard): AS-0041 (schema_v1 keeps auto_renew boolean in term section).

Every MSA has an auto_renew TermSet field; it is a bool and cites the same section (doc and anchor) as expiration_date.
Keyed on field names and sections only (no stub template text), so it applies unchanged to schema_v1. Sources are
compared directly, not through contracts.same_section, so the rule's own mutations cannot make this pass vacuously."""
from brief import contracts


def _msa_fields(real_facts):
    for sid in sorted(real_facts):
        for did, (meta, _secs, _p) in contracts.system_docs(sid).items():
            if meta.get("doc_type") == "MSA":
                yield did, {k: f for d, k, f in contracts.system_terms(sid) if d == did}


def test_auto_renew_present_on_every_msa(real_facts):
    msas = list(_msa_fields(real_facts))
    assert len(msas) == len(real_facts) == 180
    missing = [did for did, f in msas if "auto_renew" not in f or "expiration_date" not in f]
    assert not missing, missing[:5]


def test_auto_renew_is_bool_in_term_section(real_facts):
    bad = []
    for did, f in _msa_fields(real_facts):
        a, e = f.get("auto_renew"), f.get("expiration_date")
        if a is None or e is None:
            continue  # absence is the other test's job
        if not isinstance(a["value"], bool):
            bad.append((did, "not bool", a["value"]))
        if (a["source"]["doc_id"], a["source"]["anchor"]) != (e["source"]["doc_id"], e["source"]["anchor"]):
            bad.append((did, "not in the expiration_date section"))
    assert not bad, bad[:5]
