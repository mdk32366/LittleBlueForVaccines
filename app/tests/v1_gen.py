"""In-process schema_v1 regeneration from the app test session (gen is stdlib only), so an app-side mutation of the
generator's metric code shows in T-0064. The committed gen/out must equal it byte for byte."""
import hashlib
import sys

from brief import config

GEN = config.PROJECT / "gen"
if str(GEN) not in sys.path:
    sys.path.insert(0, str(GEN))

from bia562gen import generate as G, systems as S  # noqa: E402
from bia562gen import profile_metrics as PM  # noqa: E402,F401
from bia562gen.specs import load_spec  # noqa: E402

CSV = config.PROJECT / "data" / "BIA_562_Synthetic_Sales_Data.csv"


def regenerate(out):
    src = {"kind": "csv", "file": CSV.name, "sha256": hashlib.sha256(CSV.read_bytes()).hexdigest()}
    G.generate(load_spec("v1"), S.load_csv(CSV), out, 562, systems_source=src)
    return out
