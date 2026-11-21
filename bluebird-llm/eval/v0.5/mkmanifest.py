# Writes KINDS.SHA256 (documented format) and three sha256sum -c manifests for the v0.2 stage (review N1):
#   RUN-INPUTS.SHA256   rows, fewshot, eval.py, evalcore.py   -> RUN PIN (eval.py --expect_manifest_sha; recorded in every run json; to the laptop at E2)
#   SCORE-INPUTS.SHA256 score.py, evalcore.py, evalstats.py, rows -> SCORE PIN (score.py --expect_score_manifest_sha)
#   EVAL-INPUTS.SHA256  every file of the stage (box audit only; no script pins it, so a non-run edit never strands a finished run)
import hashlib, json, collections, os, sys
H = os.path.dirname(os.path.abspath(__file__)); os.chdir(H)
def sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()
by = collections.defaultdict(list)
for l in open("eval_rows.jsonl", "rb"): by[json.loads(l)["kind"]].append(l)
with open("KINDS.SHA256", "w") as f:
    f.write("# sha256 of the concatenation of that kind's lines from eval_rows.jsonl, in file order, each line exactly as stored (sort_keys JSON + \\n). Not sha256sum -c format.\n")
    for k in ("test", "cf", "ar", "sh", "rn", "pp"): f.write(f"{hashlib.sha256(b''.join(by[k])).hexdigest()}  kind={k} rows={len(by[k])}\n")
# @0.1: covers EVERY file in the stage (sha256sum -c format, paths relative to the stage). Run-time inputs first (the laptop-bound set the
# scripts look up by name), then everything else sorted. Excluded only: this file itself, __pycache__/ and *.pyc, runs/ (laptop outputs, copied back later).
core = ["eval_rows.jsonl", "fewshot.json", "eval.py", "evalcore.py", "score.py", "evalstats.py", "probecheck.py", "build_eval_rows.py"]
rest = sorted(os.path.relpath(os.path.join(d, f), H) for d, ds, fs in os.walk(H) for f in fs
              if "__pycache__" not in d.split(os.sep) and not f.endswith(".pyc") and not os.path.relpath(d, H).split(os.sep)[0] == "runs")
RUN = ["eval_rows.jsonl", "fewshot.json", "eval.py", "evalcore.py"]; SCORE = ["score.py", "evalcore.py", "evalstats.py", "eval_rows.jsonl"]
open("RUN-INPUTS.SHA256", "w").write("".join(f"{sha(f)}  {f}\n" for f in RUN))
open("SCORE-INPUTS.SHA256", "w").write("".join(f"{sha(f)}  {f}\n" for f in SCORE))
core += ["RUN-INPUTS.SHA256", "SCORE-INPUTS.SHA256"]
files = core + [f for f in rest if f not in core and f != "EVAL-INPUTS.SHA256"]
open("EVAL-INPUTS.SHA256", "w").write("".join(f"{sha(f)}  {f}\n" for f in files))
print(open("KINDS.SHA256").read() + open("EVAL-INPUTS.SHA256").read() + "".join(f"{m} sha256 {sha(m)}\n" for m in ("RUN-INPUTS.SHA256", "SCORE-INPUTS.SHA256", "EVAL-INPUTS.SHA256")))
