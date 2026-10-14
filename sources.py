"""
sources.py - registry of free-proxy sources (APIs + community lists).

Each source knows how to build its request URL(s) for a given
(protocol, anonymity, country) selection and how to parse the response.
A builder returns [] when the source cannot express the requested
combination of filters - that source is then skipped.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence, Set

# Proxy protocol keys used throughout the app
PROTOCOLS: Set[str] = {"http", "https", "socks4", "socks5"}
ANONYMITY_LEVELS: Set[str] = {"elite", "anonymous", "transparent"}

# GeoNode (and a few others) reject default python-requests user agents
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

PROXY_RE = re.compile(r"(\d{1,3}(?:\.\d{1,3}){3}):(\d{1,5})")

BuildFn = Callable[[Optional[str], Optional[str], Optional[str]], List[str]]
# arguments: (protocol, anonymity, country) - None means "no filter / all"


def extract_proxies(text: str) -> List[str]:
    """Pull every valid ip:port out of arbitrary text (handles protocol:// prefixes)."""
    found: List[str] = []
    for ip, port in PROXY_RE.findall(text):
        octets = ip.split(".")
        if ip == "0.0.0.0" or any(int(o) > 255 for o in octets):
            continue
        if not 1 <= int(port) <= 65535:
            continue
        found.append(f"{ip}:{port}")
    return found


def extract_geonode(text: str) -> List[str]:
    """Parse the GeoNode JSON API (ip and port live in separate fields)."""
    import json

    try:
        payload = json.loads(text)
    except ValueError:
        return []
    found: List[str] = []
    for item in payload.get("data", []):
        ip, port = item.get("ip"), item.get("port")
        if ip and port is not None:
            found.extend(extract_proxies(f"{ip}:{port}"))
    return found


@dataclass(frozen=True)
class Source:
    name: str
    kind: str          # "text" (regex ip:port) or "geonode" (JSON API)
    build: BuildFn
    protocols: Set[str]
    note: str = ""
    bulk: bool = False  # huge unchecked pools, behind the "Bulk pools" toggle

    def urls(self, protocol: str | None, anonymity: str | None, country: str | None) -> List[str]:
        return self.build(protocol, anonymity, country)

    def parse(self, body: str) -> List[str]:
        return extract_geonode(body) if self.kind == "geonode" else extract_proxies(body)


# --------------------------------------------------------------------------
# URL builders
# --------------------------------------------------------------------------

def _proxyscrape_v4(p: str | None, a: str | None, c: str | None) -> List[str]:
    q = "request=display_proxies&proxy_format=ipport&format=text"
    if p:
        q += f"&protocol={p}"
    if a:
        q += f"&anonymity={a}"
    if c:
        q += f"&country={c.lower()}"
    return [f"https://api.proxyscrape.com/v4/free-proxy-list/get?{q}"]


def _proxyscrape_v2(p: str | None, a: str | None, c: str | None) -> List[str]:
    proto = {"https": "http"}.get(p, p) or "http"  # v2 folds https into http
    q = (
        f"request=displayproxies&protocol={proto}&timeout=10000"
        f"&country={c.lower() if c else 'all'}&ssl=all&anonymity={a or 'all'}"
    )
    return [f"https://api.proxyscrape.com/v2/?{q}"]


def _geonode(p: str | None, a: str | None, c: str | None) -> List[str]:
    q = "limit=500&page=1&sort_by=lastChecked&sort_type=desc"
    if p:
        q += f"&protocols={p}"
    if a:
        q += f"&anonymityLevel={a}"
    if c:
        q += f"&country={c.upper()}"
    return [f"https://proxylist.geonode.com/api/proxy-list?{q}"]


_PS_MIRROR = "https://cdn.jsdelivr.net/gh/proxyscrape/free-proxy-list@main/proxies"


def _proxyscrape_mirror(p: str | None, a: str | None, c: str | None) -> List[str]:
    if a:  # no per-anonymity files in this mirror
        return []
    if c and p:
        return [f"{_PS_MIRROR}/countries/{c.lower()}/{p}/data.txt"]
    if c:
        return [f"{_PS_MIRROR}/countries/{c.lower()}/data.txt"]
    if p:
        return [f"{_PS_MIRROR}/protocols/{p}/data.txt"]
    return [f"{_PS_MIRROR}/all/data.txt"]


def _clearproxy(p: str | None, a: str | None, c: str | None) -> List[str]:
    if a:  # no anonymity files
        return []
    proto = {"https": "http"}.get(p, p) or "http"
    base = "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main"
    if c:
        return [f"{base}/{proto}/raw/country/{c.upper()}.txt"]
    return [f"{base}/{proto}/raw/all.txt"]


def _thordata(p: str | None, a: str | None, c: str | None) -> List[str]:
    base = "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies"
    if sum(x is not None for x in (p, a, c)) > 1:
        return []  # files are split by ONE dimension only
    if c:
        return [f"{base}/by-country/{c.upper()}.txt"]
    if a:
        return [f"{base}/{'high-anon' if a == 'elite' else a}.txt"]
    if p:
        return [f"{base}/{p}.txt"]
    return [f"{base}/all.txt"]


def _github_list(
    raw_base: str,
    names: dict[str | None, Sequence[str]],
    p: str | None, a: str | None, c: str | None,
) -> List[str]:
    """Static raw.githubusercontent / CDN lists: optional per-protocol files."""
    if a or c:
        return []
    keys = ["http", "https", "socks4", "socks5"] if p is None else [p]
    urls: List[str] = []
    for key in keys:
        for name in names.get(key, ()):
            urls.append(f"{raw_base}/{name}")
    return urls


def _speedx(p, a, c):
    return _github_list(
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master",
        {"http": ["http.txt"], "https": ["http.txt"],
         "socks4": ["socks4.txt"], "socks5": ["socks5.txt"]}, p, a, c)


def _monosans(p, a, c):
    return _github_list(
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies",
        {"http": ["http.txt"], "https": ["http.txt"],
         "socks4": ["socks4.txt"], "socks5": ["socks5.txt"]}, p, a, c)


def _iplocate(p, a, c):
    return _github_list(
        "https://raw.githubusercontent.com/iplocate/free-proxy-list/main/protocols",
        {"http": ["http.txt"], "https": ["https.txt"],
         "socks4": ["socks4.txt"], "socks5": ["socks5.txt"]}, p, a, c)


def _proxifly(p, a, c):
    return _github_list(
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols",
        {"http": ["http/data.txt"], "https": ["https/data.txt"],
         "socks4": ["socks4/data.txt"], "socks5": ["socks5/data.txt"]}, p, a, c)


def _shiftytr(p, a, c):
    return _github_list(
        "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master",
        {"http": ["http.txt"], "https": ["https.txt"],
         "socks4": ["socks4.txt"], "socks5": ["socks5.txt"]}, p, a, c)


def _mmpx12(p, a, c):
    return _github_list(
        "https://raw.githubusercontent.com/mmpx12/proxy-list/master",
        {"http": ["http.txt"], "https": ["https.txt"],
         "socks4": ["socks4.txt"], "socks5": ["socks5.txt"]}, p, a, c)


def _roosterkid(p, a, c):
    return _github_list(
        "https://raw.githubusercontent.com/roosterkid/openproxylist/main",
        {"http": ["HTTPS_RAW.txt"], "https": ["HTTPS_RAW.txt"],
         "socks4": ["SOCKS4_RAW.txt"], "socks5": ["SOCKS5_RAW.txt"]}, p, a, c)


def _vakhov(p, a, c):
    return _github_list(
        "https://raw.githubusercontent.com/vakhov/fresh-proxy-list/master",
        {"http": ["http.txt"], "https": ["https.txt"],
         "socks4": ["socks4.txt"], "socks5": ["socks5.txt"]}, p, a, c)


def _kangproxy(p, a, c):
    return _github_list(
        "https://cdn.jsdelivr.net/gh/officialputuid/KangProxy@main",
        {"http": ["http/http.txt"], "https": ["https/https.txt"],
         "socks4": ["socks4/socks4.txt"], "socks5": ["socks5/socks5.txt"]}, p, a, c)


def _mupig(p, a, c):
    return _github_list(
        "https://raw.githubusercontent.com/MuRongPIG/Proxy-Master/main",
        {"http": ["http.txt"], "https": ["https.txt"],
         "socks4": ["socks4.txt"], "socks5": ["socks5.txt"]}, p, a, c)


def _gfpcom(p, a, c):
    return _github_list(
        "https://raw.githubusercontent.com/wiki/gfpcom/free-proxy-list/lists",
        {"http": ["http.txt"], "https": ["https.txt"],
         "socks4": ["socks4.txt"], "socks5": ["socks5.txt"]}, p, a, c)


def _hookzof(p, a, c):
    return _github_list(
        "https://raw.githubusercontent.com/hookzof/socks5_list/master",
        {"socks5": ["proxy.txt"]}, p, a, c)


# --------------------------------------------------------------------------
# The registry
# --------------------------------------------------------------------------

SOURCES: List[Source] = [
    # --- APIs with native country + anonymity filtering ---
    Source("ProxyScrape v4", "text", _proxyscrape_v4, PROTOCOLS,
           "official free API - proto/anonymity/country filters"),
    Source("ProxyScrape v2", "text", _proxyscrape_v2, {"http", "https", "socks4", "socks5"},
           "legacy API - proto/anonymity/country filters"),
    Source("GeoNode", "geonode", _geonode, PROTOCOLS,
           "JSON API - proto/anonymity/country filters"),
    # --- mirrors / checked lists with country files ---
    Source("ProxyScrape mirror", "text", _proxyscrape_mirror, PROTOCOLS,
           "GitHub+jsDelivr mirror - proto/country files"),
    Source("ClearProxy checked", "text", _clearproxy, PROTOCOLS,
           "checked every 5 min - proto/country files"),
    Source("Thordata awesome", "text", _thordata, PROTOCOLS,
           "validated+geo - proto OR anonymity OR country files"),
    # --- community lists (protocol filter only) ---
    Source("TheSpeedX", "text", _speedx, {"http", "https", "socks4", "socks5"},
           "daily-updated classic list"),
    Source("monosans", "text", _monosans, {"http", "https", "socks4", "socks5"},
           "small curated list"),
    Source("iplocate", "text", _iplocate, PROTOCOLS,
           "revalidated every 30 min"),
    Source("Proxifly", "text", _proxifly, PROTOCOLS,
           "community list"),
    Source("ShiftyTR", "text", _shiftytr, PROTOCOLS,
           "community list"),
    Source("mmpx12", "text", _mmpx12, PROTOCOLS,
           "community list"),
    Source("roosterkid", "text", _roosterkid, {"http", "https", "socks4", "socks5"},
           "community list"),
    Source("vakhov fresh", "text", _vakhov, PROTOCOLS,
           "fresh-proxy-list"),
    Source("KangProxy", "text", _kangproxy, PROTOCOLS,
           "community list via jsDelivr"),
    # --- bulk pools (huge, unchecked) - behind the toggle ---
    Source("MuRongPIG pool", "text", _mupig, PROTOCOLS,
           "unchecked bulk pool (~100k per proto)", bulk=True),
    Source("GFP pool", "text", _gfpcom, PROTOCOLS,
           "unchecked bulk pool (500k+ per proto)", bulk=True),
    Source("hookzof socks5", "text", _hookzof, {"socks5"},
           "unchecked bulk pool (socks5)", bulk=True),
]
