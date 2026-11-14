"""T-0065 (app part): the gen/out manifest's benchmark_source is the app's national file by sha256, and the national
figures in every EXH1 equal the app's own national_profile ratios. Mutation: nat_profile_r1."""
import json
import math
from pathlib import Path

from brief import benchmark as bm, client_metrics, config, load


def test_manifest_sha_is_the_national_file():
    m = json.loads((config.GEN_OUT / "manifest.json").read_text())
    b = m["benchmark_source"]
    assert b["file"] == bm.NATIONAL_FILE
    assert b["sha256"] == load.sha256_file(bm.national_path())


def test_exhibit_national_ratios_equal_app_profile(real_national):
    want = {r: client_metrics.ratio_rule(real_national[n], real_national[d])[0]
            for r, (n, d) in client_metrics.RATIOS.items()}
    files = sorted(Path(config.GEN_OUT).glob("*/docs/SYN-*-EXH1.terms.json"))
    assert len(files) == 180
    for p in files:
        for k, f in json.loads(p.read_text())["fields"].items():
            item = f["qualifier"].get("item")
            if k.startswith("nat_ratio-") and item in want:
                assert math.isclose(f["value"], want[item], rel_tol=1e-9), (p.name, item, f["value"], want[item])
