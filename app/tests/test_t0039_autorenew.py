"""T-0039 (pending Trinity's numbering) auto-renew marker, field-based (AS-0040 (expired rule)), and T-0041 (pending)
schema_v1 auto_renew contract (AS-0041 (schema_v1 keeps auto_renew boolean in term section)).

The rule: an expired MSA shows [TERM ENDED · auto-renews] iff its TermSet auto_renew field is True AND cites the same
section as expiration_date (span verbatim there); otherwise [EXPIRED]. No phrase matching anywhere."""
from brief import config, contracts

SECTION = {"text": "The Agreement remains in force through August 31, 2026. It renews automatically."}
DOCS = {"SYN-SYNCPX-MSA1": ({}, {"2": SECTION, "8": {"text": "renews automatically"}}, None)}
EXP = {"value": "2026-08-31", "span": "August 31, 2026", "source": {"doc_id": "SYN-SYNCPX-MSA1", "anchor": "2"}}


def _auto(value, anchor="2", span="renews automatically"):
    return {"value": value, "span": span, "source": {"doc_id": "SYN-SYNCPX-MSA1", "anchor": anchor}}


def test_rule_unit_cases():
    m = contracts.field_marker
    assert m("expiration_date", EXP, [_auto(True)], DOCS) == contracts.AUTO_RENEW_MARKER
    assert m("expiration_date", EXP, [_auto(False)], DOCS) == contracts.EXPIRED_MARKER
    assert m("expiration_date", EXP, [], DOCS) == contracts.EXPIRED_MARKER
    # auto_renew True but cited in ANOTHER section -> not the same term span -> [EXPIRED]
    assert m("expiration_date", EXP, [_auto(True, anchor="8")], DOCS) == contracts.EXPIRED_MARKER
    # span not verbatim in the cited section -> [EXPIRED]
    assert m("expiration_date", EXP, [_auto(True, span="rolls over")], DOCS) == contracts.EXPIRED_MARKER
    # a live contract never gets a marker, whatever auto_renew says
    live = dict(EXP, value=config.AS_OF_DATE)
    assert m("expiration_date", live, [_auto(True)], DOCS) == ""


def test_rule_ignores_clause_wording():
    """Field-based: changing the sentence wording (keeping the span verbatim) does not change the marker."""
    docs = {"SYN-SYNCPX-MSA1": ({}, {"2": {"text": "Term ends August 31, 2026. Evergreen: zzz qqq."}}, None)}
    assert contracts.field_marker("expiration_date", EXP, [_auto(True, span="zzz qqq")], docs) == contracts.AUTO_RENEW_MARKER


def test_pre_regen_split_9_12_stub_data(real_facts):
    """PRE-REGEN (stub-v0 gen/out at manifest a16eb5a0; superseded by the GATE 2 count pin after the schema_v1
    regeneration). NOT the final count pin: 21 expired = 9 auto-renew + 12 none, exact ids; edges 094/095/096 live."""
    auto, none = [], []
    for sid in sorted(real_facts):
        for h in contracts.lookup(sid, base="expiration_date"):
            if h["marker"] == contracts.AUTO_RENEW_MARKER:
                auto.append(sid)
            elif h["marker"] == contracts.EXPIRED_MARKER:
                none.append(sid)
    ids = lambda xs: ["SYNCP000" + x for x in xs.split()]  # noqa: E731
    assert auto == ids("007 009 018 036 062 088 099 140 150"), auto
    assert none == ids("014 068 083 090 101 130 135 141 146 148 149 164"), none
    assert len(auto) + len(none) == 21
    for sid in ids("094 095 096"):
        assert all(h["marker"] == "" and not h["expired"] for h in contracts.lookup(sid, base="expiration_date")), sid


def test_status_column_and_citations_use_marker():
    marks = contracts.system_markers("SYNCP000036")
    assert marks[("SYN-SYNCP000036-MSA1", "expiration_date")] == contracts.AUTO_RENEW_MARKER
    assert contracts.system_markers("SYNCP000014")[("SYN-SYNCP000014-MSA1", "expiration_date")] == contracts.EXPIRED_MARKER
    cites = contracts.answer("SYNCP000036", "When does the MSA expire?")["citations"]
    assert cites and all(h["marker"] == contracts.AUTO_RENEW_MARKER for h in cites)


def test_schema_auto_renew_bool_in_term_section(real_facts):
    """AS-0041: every MSA has an auto_renew TermSet field that is a bool and cites the same section as expiration_date.
    Keyed on field names and sections only (no stub template text), so it applies unchanged to schema_v1."""
    n = 0
    for sid in sorted(real_facts):
        for did, (meta, _secs, _p) in contracts.system_docs(sid).items():
            if meta.get("doc_type") != "MSA":
                continue
            fields = {k: f for d, k, f in contracts.system_terms(sid) if d == did}
            assert "auto_renew" in fields, (did, "auto_renew missing")
            assert "expiration_date" in fields, (did, "expiration_date missing")
            assert isinstance(fields["auto_renew"]["value"], bool), (did, fields["auto_renew"]["value"])
            a, e = fields["auto_renew"]["source"], fields["expiration_date"]["source"]
            assert (a["doc_id"], a["anchor"]) == (e["doc_id"], e["anchor"]), did  # compared directly, not via the rule
            n += 1
    assert n == len(real_facts) == 180
