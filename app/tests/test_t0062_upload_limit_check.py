"""T-0062 upload limits are equal (F-0026). `tools/upload_limit_check.py` is the check the deploy runs against its
own reverse-proxy Caddyfile and Streamlit config.toml (both outside this repository, Q-M7). The snippets below are
minimal stand-ins, not the deploy files.
Mutation: upload_si (Caddy's MiB/KiB/GiB read as base 1000, so 10MiB no longer equals Streamlit's 10)."""
import pytest

from tools import upload_limit_check as ulc

CADDY = """# stand-in
:8502 {{
	@upload path /_stcore/upload_file/*
	request_body @upload {{
		max_size {size}
	}}
}}
"""
CONF = "[server]\nmaxUploadSize = {mb}\n"


def test_caddy_sizes_in_bytes():
    assert ulc.caddy_bytes("10MiB") == 10_485_760 == ulc.caddy_bytes("10mi")
    assert ulc.caddy_bytes("10MB") == 10_000_000 == ulc.caddy_bytes("10M")
    assert ulc.caddy_bytes("512KiB") == 524_288 and ulc.caddy_bytes("1GiB") == 2 ** 30
    assert ulc.caddy_bytes("4096") == 4096
    for bad in ("", "MiB", "10 parsecs", "-1MB"):
        with pytest.raises(ValueError):
            ulc.caddy_bytes(bad)


def test_streamlit_bytes():
    assert ulc.streamlit_bytes(CONF.format(mb=10)) == 10_485_760
    assert ulc.streamlit_bytes("[server]\nheadless = true\n") == 200 * 1024 * 1024  # Streamlit's default
    for bad in ("0", "-1", '"10"', "true"):
        with pytest.raises(ValueError):
            ulc.streamlit_bytes(CONF.format(mb=bad))


def test_equal_limits_pass(tmp_path, capsys):
    (tmp_path / "Caddyfile").write_text(CADDY.format(size="10MiB"))
    (tmp_path / "config.toml").write_text(CONF.format(mb=10))
    rc = ulc.main(["--caddyfile", str(tmp_path / "Caddyfile"), "--streamlit-config", str(tmp_path / "config.toml")])
    out = capsys.readouterr().out
    assert rc == 0 and out.startswith("UPLOAD_LIMITS PASS") and "10,485,760 B" in out, out


def test_deploy2_limits_fail(tmp_path, capsys):
    """The Deploy-2 pairing (Caddy 10MB, Streamlit 10) is unequal: the proxy cuts at 10,000,000 B."""
    (tmp_path / "Caddyfile").write_text(CADDY.format(size="10MB"))
    (tmp_path / "config.toml").write_text(CONF.format(mb=10))
    rc = ulc.main(["--caddyfile", str(tmp_path / "Caddyfile"), "--streamlit-config", str(tmp_path / "config.toml")])
    out = capsys.readouterr().out
    assert rc == 1 and out.startswith("UPLOAD_LIMITS FAIL") and "10,000,000 B" in out and "10MiB" in out, out


def test_exactly_one_max_size(tmp_path, capsys):
    assert ulc.caddy_max_size(CADDY.format(size="10MiB") + "# max_size 1MB in a comment\n") == "10MiB"
    with pytest.raises(ValueError):
        ulc.caddy_max_size(":8502 {\n\treverse_proxy app:8501\n}\n")
    with pytest.raises(ValueError):
        ulc.caddy_max_size(CADDY.format(size="10MiB") * 2)
    (tmp_path / "Caddyfile").write_text(":8502 {\n}\n")
    (tmp_path / "config.toml").write_text(CONF.format(mb=10))
    rc = ulc.main(["--caddyfile", str(tmp_path / "Caddyfile"), "--streamlit-config", str(tmp_path / "config.toml")])
    assert rc == 2 and capsys.readouterr().out.startswith("UPLOAD_LIMITS ERROR")
    rc = ulc.main(["--caddyfile", str(tmp_path / "missing"), "--streamlit-config", str(tmp_path / "config.toml")])
    assert rc == 2
