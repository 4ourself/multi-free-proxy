from __future__ import annotations

import json
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass

PROTOCOLS: set[str] = {"http", "https", "socks4", "socks5"}
ANONYMITY_LEVELS: set[str] = {"elite", "anonymous", "transparent"}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

PROXY_RE = re.compile(r"(\d{1,3}(?:\.\d{1,3}){3}):(\d{1,5})")

BuildFn = Callable[[str | None, str | None, str | None], list[str]]


def extract_proxies(text: str) -> list[str]:
    found: list[str] = []
    for ip, port in PROXY_RE.findall(text):
        octets = ip.split(".")
        if ip == "0.0.0.0" or any(int(o) > 255 for o in octets):
            continue
        if not 1 <= int(port) <= 65535:
            continue
        found.append(f"{ip}:{port}")
    return found


def extract_geonode(text: str) -> list[str]:
    try:
        payload = json.loads(text)
    except ValueError:
        return []
    found: list[str] = []
    for item in payload.get("data", []):
        ip, port = item.get("ip"), item.get("port")
        if ip and port is not None:
            found.extend(extract_proxies(f"{ip}:{port}"))
    return found


@dataclass(frozen=True)
class Source:
    name: str
    kind: str
    build: BuildFn
    protocols: set[str]
    note: str = ""
    bulk: bool = False

    def urls(self, protocol: str | None, anonymity: str | None, country: str | None) -> list[str]:
        return self.build(protocol, anonymity, country)


def _proxyscrape_v4(p: str | None, a: str | None, c: str | None) -> list[str]:
    q = "request=display_proxies&proxy_format=ipport&format=text"
    if p:
        q += f"&protocol={p}"
    if a:
        q += f"&anonymity={a}"
    if c:
        q += f"&country={c.lower()}"
    return [f"https://api.proxyscrape.com/v4/free-proxy-list/get?{q}"]


def _proxyscrape_v2(p: str | None, a: str | None, c: str | None) -> list[str]:
    proto = {"https": "http"}.get(p, p) or "http"
    q = (
        f"request=displayproxies&protocol={proto}&timeout=10000"
        f"&country={c.lower() if c else 'all'}&ssl=all&anonymity={a or 'all'}"
    )
    return [f"https://api.proxyscrape.com/v2/?{q}"]


def _geonode(p: str | None, a: str | None, c: str | None) -> list[str]:
    q = "limit=500&page=1&sort_by=lastChecked&sort_type=desc"
    if p:
        q += f"&protocols={p}"
    if a:
        q += f"&anonymityLevel={a}"
    if c:
        q += f"&country={c.upper()}"
    return [f"https://proxylist.geonode.com/api/proxy-list?{q}"]


_PS_MIRROR = "https://cdn.jsdelivr.net/gh/proxyscrape/free-proxy-list@main/proxies"


def _proxyscrape_mirror(p: str | None, a: str | None, c: str | None) -> list[str]:
    if a:
        return []
    if c and p:
        return [f"{_PS_MIRROR}/countries/{c.lower()}/{p}/data.txt"]
    if c:
        return [f"{_PS_MIRROR}/countries/{c.lower()}/data.txt"]
    if p:
        return [f"{_PS_MIRROR}/protocols/{p}/data.txt"]
    return [f"{_PS_MIRROR}/all/data.txt"]


def _clearproxy(p: str | None, a: str | None, c: str | None) -> list[str]:
    if a:
        return []
    proto = {"https": "http"}.get(p, p) or "http"
    base = "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main"
    if c:
        return [f"{base}/{proto}/raw/country/{c.upper()}.txt"]
    return [f"{base}/{proto}/raw/all.txt"]


def _thordata(p: str | None, a: str | None, c: str | None) -> list[str]:
    base = "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies"
    if sum(x is not None for x in (p, a, c)) > 1:
        return []
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
) -> list[str]:
    if a or c:
        return []
    keys = ["http", "https", "socks4", "socks5"] if p is None else [p]
    return [f"{raw_base}/{name}" for key in keys for name in names.get(key, ())]


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


SOURCES: list[Source] = [
    Source("ProxyScrape v4", "text", _proxyscrape_v4, PROTOCOLS,
           "API, protocol/anonymity/country"),
    Source("ProxyScrape v2", "text", _proxyscrape_v2, PROTOCOLS,
           "API, protocol/anonymity/country"),
    Source("GeoNode", "geonode", _geonode, PROTOCOLS,
           "API, protocol/anonymity/country"),
    Source("ProxyScrape mirror", "text", _proxyscrape_mirror, PROTOCOLS,
           "mirror, protocol/country"),
    Source("ClearProxy checked", "text", _clearproxy, PROTOCOLS,
           "checked list, protocol/country"),
    Source("Thordata awesome", "text", _thordata, PROTOCOLS,
           "checked list, protocol/anonymity/country"),
    Source("TheSpeedX", "text", _speedx, PROTOCOLS,
           "community list"),
    Source("monosans", "text", _monosans, PROTOCOLS,
           "community list"),
    Source("iplocate", "text", _iplocate, PROTOCOLS,
           "community list"),
    Source("Proxifly", "text", _proxifly, PROTOCOLS,
           "community list"),
    Source("ShiftyTR", "text", _shiftytr, PROTOCOLS,
           "community list"),
    Source("mmpx12", "text", _mmpx12, PROTOCOLS,
           "community list"),
    Source("roosterkid", "text", _roosterkid, PROTOCOLS,
           "community list"),
    Source("vakhov fresh", "text", _vakhov, PROTOCOLS,
           "community list"),
    Source("KangProxy", "text", _kangproxy, PROTOCOLS,
           "community list"),
    Source("MuRongPIG pool", "text", _mupig, PROTOCOLS,
           "bulk pool, unchecked", bulk=True),
    Source("GFP pool", "text", _gfpcom, PROTOCOLS,
           "bulk pool, unchecked", bulk=True),
    Source("hookzof socks5", "text", _hookzof, {"socks5"},
           "bulk pool, unchecked", bulk=True),
]
