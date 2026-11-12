#!/usr/bin/env python3
"""Headless Streamlit smoke: start on localhost, hit /_stcore/health and /, run the AppTest checks, stop the server."""
import os, signal, subprocess, sys, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / ".venv" / "bin"
if not BIN.exists():  # clean clone / CI: the interpreter running this script
    BIN = Path(sys.executable).parent
PORT = int(os.environ.get("SMOKE_PORT", "8599"))
lines = []


def log(s):
    print(s, flush=True)
    lines.append(s)


env = dict(os.environ, STREAMLIT_BROWSER_GATHER_USAGE_STATS="false")
proc = subprocess.Popen([str(BIN / "streamlit"), "run", str(ROOT / "app.py"), "--server.headless", "true",
                         "--server.address", "127.0.0.1", "--server.port", str(PORT)],
                        cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                        start_new_session=True)
ok = True
try:
    health = None
    for _ in range(60):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/_stcore/health", timeout=2) as r:
                health = (r.status, r.read().decode())
                break
        except Exception:
            time.sleep(1)
    log(f"server pid={proc.pid} port={PORT}")
    log(f"GET /_stcore/health -> {health}")
    ok &= health == (200, "ok")
    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/", timeout=5) as r:
        log(f"GET / -> {r.status} ({len(r.read())} bytes)")
        ok &= r.status == 200
    t = subprocess.run([str(BIN / "python"), "-m", "pytest", "-v", "-p", "no:cacheprovider", "tests/test_app.py",
                        "tests/test_t0035_name.py"], cwd=ROOT, capture_output=True, text=True)
    log("AppTest (picker, brief, Q&A tab, download button, benchmark toggle, page title/header):")
    log("\n".join(l for l in t.stdout.splitlines() if "PASSED" in l or "FAILED" in l or "passed" in l or "failed" in l))
    ok &= t.returncode == 0
finally:
    os.killpg(proc.pid, signal.SIGTERM)
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait()
    log(f"server stopped: returncode={proc.returncode}")
log(f"SMOKE: {'PASS' if ok else 'FAIL'}")
(ROOT / "evidence").mkdir(exist_ok=True)
(ROOT / "evidence" / "smoke.txt").write_text("\n".join(lines) + "\n")
sys.exit(0 if ok else 1)
