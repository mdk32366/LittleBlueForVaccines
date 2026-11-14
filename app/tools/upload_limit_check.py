#!/usr/bin/env python3
"""Upload-limit check (T-0062, F-0026). The deploy runs it against the deploy's own files, which stay outside this
repository (Q-M7): the per-app reverse-proxy Caddyfile and the Streamlit config.toml baked into the image.
It passes only when Caddy's request_body max_size equals Streamlit's server.maxUploadSize, both in bytes.

  python tools/upload_limit_check.py --caddyfile <path> --streamlit-config <path>

Streamlit reads maxUploadSize in megabytes of 1024 * 1024 bytes (default 200). Caddy sizes follow go-humanize:
"MB" and "M" are 1000 ** 2, "MiB" and "Mi" are 1024 ** 2, and a bare number is bytes. So Streamlit 10 needs Caddy
"10MiB" (10,485,760 B); "10MB" is 10,000,000 B, which makes the proxy the tighter limit.
Exit 0 on PASS, 1 on FAIL, 2 on a file it can't read or parse."""
import argparse
import re
import sys
import tomllib

STREAMLIT_DEFAULT_MB = 200
STREAMLIT_UNIT = 1024 * 1024
CADDY_UNITS = {"": 1, "b": 1,
               "k": 1000, "kb": 1000, "ki": 1024, "kib": 1024,
               "m": 1000 ** 2, "mb": 1000 ** 2, "mi": 1024 ** 2, "mib": 1024 ** 2,
               "g": 1000 ** 3, "gb": 1000 ** 3, "gi": 1024 ** 3, "gib": 1024 ** 3}
_SIZE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([a-z]*)\s*$", re.I)
_MAX_SIZE = re.compile(r"^\s*max_size\s+(\S+)\s*$", re.M)
_COMMENT = re.compile(r"(^|\s)#.*$", re.M)


def caddy_bytes(size: str) -> int:
    m = _SIZE.match(size)
    if not m or m.group(2).lower() not in CADDY_UNITS:
        raise ValueError(f"not a Caddy size: {size!r}")
    return int(float(m.group(1)) * CADDY_UNITS[m.group(2).lower()])


def streamlit_bytes(config_text: str) -> int:
    mb = tomllib.loads(config_text).get("server", {}).get("maxUploadSize", STREAMLIT_DEFAULT_MB)
    if isinstance(mb, bool) or not isinstance(mb, int) or mb <= 0:
        raise ValueError(f"server.maxUploadSize must be a positive integer (MB), got {mb!r}")
    return mb * STREAMLIT_UNIT


def caddy_max_size(caddyfile_text: str) -> str:
    """The one request_body max_size in the Caddyfile (comments ignored); more or fewer than one is an error."""
    sizes = _MAX_SIZE.findall(_COMMENT.sub(r"\1", caddyfile_text))
    if len(sizes) != 1:
        raise ValueError(f"expected exactly one request_body max_size, found {len(sizes)}: {sizes}")
    return sizes[0]


def check(caddyfile_text: str, config_text: str) -> tuple[bool, str]:
    raw = caddy_max_size(caddyfile_text)
    c, s = caddy_bytes(raw), streamlit_bytes(config_text)
    ok = c == s
    detail = (f"caddy max_size {raw} = {c:,} B; streamlit maxUploadSize = {s:,} B "
              f"({s // STREAMLIT_UNIT} MB of 1024*1024)")
    if not ok:
        detail += f"; set Caddy max_size to {s // STREAMLIT_UNIT}MiB" if s % STREAMLIT_UNIT == 0 else ""
    return ok, detail


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--caddyfile", required=True)
    ap.add_argument("--streamlit-config", required=True)
    a = ap.parse_args(argv)
    try:
        with open(a.caddyfile, encoding="utf-8") as f:
            caddy = f.read()
        with open(a.streamlit_config, encoding="utf-8") as f:
            conf = f.read()
        ok, detail = check(caddy, conf)
    except (OSError, ValueError, tomllib.TOMLDecodeError) as e:
        print(f"UPLOAD_LIMITS ERROR {e}")
        return 2
    print(f"UPLOAD_LIMITS {'PASS' if ok else 'FAIL'} {detail}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
