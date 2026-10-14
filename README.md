# multi-free-proxy

Download free proxies from **multiple public sources at once** — filterable by
protocol, anonymity and country — straight from your terminal.

```
====================================
  Multi-Free-Proxy  -  free proxies from multiple sources
====================================
protocol: http | anonymity: all | country: all | bulk pools: off
  [1] Download proxies
  [2] Protocol
  [3] Anonymity
  [4] Country
  [5] Bulk pools      (off)
  [6] List sources
  [0] Exit
```

## Features

- **18 sources** — public APIs (ProxyScrape, GeoNode) + community GitHub lists,
  queried in parallel and merged into one deduplicated list
- **Filter by protocol** — `http`, `https`, `socks4`, `socks5`, or all
- **Filter by anonymity** — `elite`, `anonymous`, `transparent`
- **Filter by country** — ISO-2 code (`us`, `de`, `kz`, ...) where the source supports it
- **Bulk pools toggle** — opt-in to huge unchecked pools (500k+ raw entries)
- **Terminal UI only** — no web UI, no extra frameworks
- **Output: `proxy.txt`** — plain `ip:port` lines, sorted, in this folder
- **Self-healing start** — `start.bat` runs the app first and only installs
  libraries if Python reports one is missing

## Quick start

**Windows**

```
start.bat
```

That's it. `start.bat` runs `python main.py` first. If (and only if) it fails
with a missing-library error, it runs `pip install -r requirements.txt` and
starts the app again. If `main.py` runs fine, **nothing is installed**.

**Any OS / manual**

```bash
python -m pip install -r requirements.txt
python main.py
```

## Options

| Setting | Choices | Notes |
|---|---|---|
| Protocol | http / https / socks4 / socks5 / all | default: http |
| Anonymity | elite / anonymous / transparent / all | elite hides your IP best |
| Country | ISO-2 code or all | sources without country files are skipped while a filter is active |
| Bulk pools | on / off | huge unchecked pools; more raw proxies, lower quality |

Sources that can't apply the selected filters (e.g. a plain list with no
country data) are automatically skipped — the sources screen shows which ones
match. Filters combine, so `elite` + `us` uses the APIs that support both.

## CLI (optional)

Skip the menu for scripting/cron:

```bash
python main.py --protocol socks5 --anonymity elite --country us
python main.py --protocol https --bulk --output my_proxies.txt
```

## Sources (tested live, Oct 2026)

| Source | Type | Filters |
|---|---|---|
| ProxyScrape v4 | API | protocol, anonymity, country |
| ProxyScrape v2 | API | protocol, anonymity, country |
| GeoNode | JSON API | protocol, anonymity, country |
| ProxyScrape mirror | jsDelivr mirror | protocol, country |
| ClearProxy checked | checked list | protocol, country |
| Thordata awesome | validated list | protocol / anonymity / country |
| TheSpeedX | community list | protocol |
| monosans | community list | protocol |
| iplocate | revalidated list | protocol |
| Proxifly | community list | protocol |
| ShiftyTR | community list | protocol |
| mmpx12 | community list | protocol |
| roosterkid | community list | protocol |
| vakhov fresh | community list | protocol |
| KangProxy | community list | protocol |
| MuRongPIG pool *(bulk)* | unchecked pool | protocol |
| GFP pool *(bulk)* | unchecked pool | protocol |
| hookzof socks5 *(bulk)* | unchecked pool | socks5 |

Research notes: dozens of free-proxy sites were reviewed. Sources that are
HTML-only (spys.one, freeproxy.world, proxylistplus, hidemy.name, ...) or dead
(`pubproxy.com` — TLS failure, `proxy-list.download` — 502 at test time) are
not included. Adding a source is a one-entry change in `sources.py`.

## Project layout

```
multi-free-proxy/
├── main.py           # terminal UI + downloader
├── sources.py        # source registry (URL builders + parsers)
├── start.bat         # runs the app; auto-installs libs ONLY if missing
├── requirements.txt  # requests, colorama
├── LICENSE
└── proxy.txt         # created on first download (git-ignored)
```

## Disclaimer

Free public proxies are shared, unreliable and often short-lived — always
expect a high failure rate and never trust them with sensitive traffic.
Use proxies only where it is legal and permitted, and respect the terms of the
websites you visit. This tool is provided as-is, without any warranty.

## License

[MIT](LICENSE)
