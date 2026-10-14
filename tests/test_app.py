"""
Offline tests for multi-free-proxy - no network access needed.

Run with:  python -m pytest
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from main import Settings, select_sources  # noqa: E402
from sources import SOURCES, extract_geonode, extract_proxies  # noqa: E402


def test_extract_proxies():
    text = "1.2.3.4:8080\njunk\n5.6.7.8:3128\r\nhttp://9.9.9.9:80"
    assert extract_proxies(text) == ["1.2.3.4:8080", "5.6.7.8:3128", "9.9.9.9:80"]


def test_extract_rejects_bad_values():
    bad = "999.1.1.1:80 1.2.3.4:99999 0.0.0.0:80 1.2.3.4:0 1.2.3.256:80 1.2.3.4:-1"
    assert extract_proxies(bad) == []


def test_extract_geonode_json():
    body = json.dumps({"data": [
        {"ip": "1.2.3.4", "port": "8080"},
        {"ip": "5.6.7.8", "port": 1080},
        {"ip": "bad", "port": None},
    ]})
    assert extract_geonode(body) == ["1.2.3.4:8080", "5.6.7.8:1080"]


def test_every_source_builds_urls_without_filters():
    for src in SOURCES:
        assert src.urls(None, None, None), src.name


def test_bulk_sources_flagged():
    assert [s.name for s in SOURCES if s.bulk] == [
        "MuRongPIG pool", "GFP pool", "hookzof socks5",
    ]


def test_thordata_cannot_combine_filters():
    thordata = next(s for s in SOURCES if s.name == "Thordata awesome")
    assert thordata.urls("http", "elite", None) == []
    assert thordata.urls("http", None, "us") == []
    assert thordata.urls("http", None, None)  # one filter at a time is fine


def test_geonode_url_uses_all_filters():
    geonode = next(s for s in SOURCES if s.name == "GeoNode")
    (url,) = geonode.urls("socks5", "elite", "us")
    assert "protocols=socks5" in url
    assert "anonymityLevel=elite" in url
    assert "country=US" in url


def test_proxyscrape_v4_url_lowercases_country():
    ps = next(s for s in SOURCES if s.name == "ProxyScrape v4")
    (url,) = ps.urls("http", "transparent", "DE")
    assert "country=de" in url
    assert "anonymity=transparent" in url


def test_select_sources_skips_bulk_by_default():
    s = Settings()
    s.protocol = None  # all protocols
    names = [src.name for src, _ in select_sources(s)]
    assert len(names) == 15
    assert "GFP pool" not in names
    s.bulk = True
    names = [src.name for src, _ in select_sources(s)]
    assert len(names) == 18
    assert "GFP pool" in names


def test_select_sources_country_filter_reduces_set():
    s = Settings()          # protocol=http by default
    s.country = "us"
    names = [src.name for src, _ in select_sources(s)]
    assert names == [
        "ProxyScrape v4", "ProxyScrape v2", "GeoNode",
        "ProxyScrape mirror", "ClearProxy checked",
    ]


def test_missing_library_exits_with_code_2(tmp_path):
    """Exit code 2 is what start.bat looks for before installing anything."""
    (tmp_path / "colorama.py").write_text("raise ImportError('No module named colorama')\n")
    env = {"PYTHONPATH": str(tmp_path), "PATH": "/usr/bin:/bin"}
    proc = subprocess.run(
        [sys.executable, "main.py"], cwd=ROOT, env=env,
        capture_output=True, text=True,
    )
    assert proc.returncode == 2
    assert "Missing Python library" in proc.stdout
