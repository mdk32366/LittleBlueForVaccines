"""T-0005 fallback: LLM off, unreachable, past the timeout, or rejected twice -> templated points, no error.
No network: the 'LLM' here is an in-process stub callable."""
from brief import config, narrative


def _fs(fixture_facts):
    return fixture_facts["SYNCP800001"]


def test_llm_off_is_default(fixture_facts):
    assert config.LLM_MODE == "off"
    n = narrative.compose(_fs(fixture_facts))
    assert n.source == "templated" and n.rendered


def test_unreachable_falls_back(fixture_facts):
    def down(_j, timeout):
        raise ConnectionError("localhost:11434 refused")
    assert narrative.compose(_fs(fixture_facts), llm=down).source == "templated"


def test_timeout_falls_back(fixture_facts):
    def slow(_j, timeout):
        assert timeout == 20
        raise TimeoutError("20 s")
    assert narrative.compose(_fs(fixture_facts), llm=slow).source == "templated"


def test_rejected_twice_falls_back(fixture_facts):
    calls = []

    def digits(_j, timeout):
        calls.append(1)
        return "Pfizer share is 54%."
    n = narrative.compose(_fs(fixture_facts), llm=digits)
    assert n.source == "templated" and len(calls) == 2


def test_valid_llm_output_used(fixture_facts):
    n = narrative.compose(_fs(fixture_facts), llm=lambda j, timeout: "Pfizer holds {F4.pfizer_share} of dollars.")
    assert n.source == "llm" and "%" in n.rendered[0]
