#!/usr/bin/env python3

import argparse
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

try:
    import requests
    from colorama import Fore, Style, init as colorama_init
except ImportError as exc:
    print(f"[ERROR] Missing Python library: {getattr(exc, 'name', None) or exc}")
    print("        Run start.bat again or: python -m pip install -r requirements.txt")
    sys.exit(2)  # start.bat installs requirements when it sees this exit code

from sources import (
    ANONYMITY_LEVELS,
    PROTOCOLS,
    SOURCES,
    USER_AGENT,
    Source,
    extract_geonode,
    extract_proxies,
)

PROJECT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = PROJECT_DIR / "proxy.txt"
REQUEST_TIMEOUT = 15
MAX_WORKERS = 12

C = {
    "head": Fore.CYAN,
    "ok": Fore.GREEN,
    "warn": Fore.YELLOW,
    "err": Fore.RED,
    "dim": Style.DIM,
    "reset": Style.RESET_ALL,
}

_thread_local = threading.local()


def session() -> requests.Session:
    sess = getattr(_thread_local, "sess", None)
    if sess is None:
        sess = requests.Session()
        sess.headers["User-Agent"] = USER_AGENT
        _thread_local.sess = sess
    return sess


class Settings:
    def __init__(self) -> None:
        self.protocol: str | None = "http"
        self.anonymity: str | None = None
        self.country: str | None = None
        self.bulk: bool = False
        self.output: Path = DEFAULT_OUTPUT

    def describe(self) -> str:
        return (
            f"protocol: {self.protocol or 'all'} | anonymity: {self.anonymity or 'all'} "
            f"| country: {self.country or 'all'} | bulk pools: {'on' if self.bulk else 'off'}"
        )


def select_sources(s: Settings) -> list[tuple[Source, list[str]]]:
    chosen = []
    for src in SOURCES:
        if src.bulk and not s.bulk:
            continue
        urls = src.urls(s.protocol, s.anonymity, s.country)
        if urls:
            chosen.append((src, urls))
    return chosen


def fetch_one(url: str, kind: str) -> list[str]:
    resp = session().get(url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return extract_geonode(resp.text) if kind == "geonode" else extract_proxies(resp.text)


def url_tag(url: str) -> str:
    parts = url.rstrip("/").split("/")
    return parts[-2] if parts[-1] in ("data.txt", "proxy.txt", "all.txt") else parts[-1]


def run_download(s: Settings) -> None:
    jobs = select_sources(s)
    if not jobs:
        print(f"{C['err']}[!] No source supports this filter combination.{C['reset']}")
        print("    Try relaxing anonymity/country, or enable bulk pools.")
        return

    url_count = sum(len(u) for _, u in jobs)
    print(f"\n{C['head']}Downloading from {len(jobs)} sources ({url_count} requests)...{C['reset']}")
    print(f"{C['dim']}    filters -> {s.describe()}{C['reset']}\n")

    results: dict[str, list[str]] = {}
    raw_total = 0
    t0 = time.time()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        future_map = {}
        for src, urls in jobs:
            for url in urls:
                label = src.name if len(urls) == 1 else f"{src.name} [{url_tag(url)}]"
                future_map[pool.submit(fetch_one, url, src.kind)] = (label, url)

        for fut in as_completed(future_map):
            label, url = future_map[fut]
            try:
                proxies = fut.result()
            except Exception as exc:
                print(f"  {C['err']}[-]{C['reset']} {label:<28} failed ({type(exc).__name__})")
                continue
            results[url] = proxies
            raw_total += len(proxies)
            print(f"  {C['ok']}[+]{C['reset']} {label:<28} {len(proxies):>7,} proxies")

    merged = dict.fromkeys(
        proxy for _, urls in jobs for url in urls for proxy in results.get(url, ())
    )
    proxies = sorted(
        merged,
        key=lambda p: (tuple(int(x) for x in p.split(":")[0].split(".")), int(p.split(":")[1])),
    )

    print(f"\n{C['dim']}{'-' * 52}{C['reset']}")
    if not proxies:
        print(f"{C['warn']}[!] No proxies found - output file not written.{C['reset']}")
        return

    s.output.write_text("\n".join(proxies) + "\n", encoding="utf-8")
    print(f"  {C['ok']}unique: {len(proxies):,}{C['reset']} "
          f"(raw {raw_total:,})   time: {time.time() - t0:.1f}s")
    print(f"  saved -> {C['head']}{s.output}{C['reset']}")


def banner() -> None:
    print(C["head"] + "=" * 52)
    print("  Multi-Free-Proxy  -  free proxies from multiple sources")
    print("=" * 52 + C["reset"])


def ask(prompt: str) -> str:
    try:
        return input(prompt).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(0)


def pick_option(title: str, options: list[tuple[str | None, str]], current: str | None) -> str | None:
    print(f"\n{C['head']}{title}{C['reset']}")
    for i, (_, label) in enumerate(options, 1):
        print(f"  [{i}] {label}")
    choice = ask("> ")
    if not choice:
        return current
    if choice in ("0", "all"):
        return None
    if choice.isdigit() and 1 <= int(choice) <= len(options):
        return options[int(choice) - 1][0]
    print(f"{C['warn']}  keeping previous value{C['reset']}")
    return current


def set_protocol(s: Settings) -> None:
    opts = [(p, p) for p in ("http", "https", "socks4", "socks5")] + [(None, "all protocols")]
    s.protocol = pick_option("Protocol:", opts, s.protocol)


def set_anonymity(s: Settings) -> None:
    opts = [(a, a) for a in ("elite", "anonymous", "transparent")] + [(None, "all levels")]
    s.anonymity = pick_option("Anonymity:", opts, s.anonymity)


def set_country(s: Settings) -> None:
    print(f"\n{C['head']}Country:{C['reset']}")
    print("  ISO-2 code (us, de, kz ...)  |  'all' for every country")
    code = ask("> ")
    if not code:
        return
    if code in ("all", "0"):
        s.country = None
    elif len(code) == 2 and code.isalpha():
        s.country = code
    else:
        print(f"{C['warn']}  invalid country code, keeping previous value{C['reset']}")


def show_sources(s: Settings) -> None:
    print(f"\n{C['head']}Sources:{C['reset']}")
    active = {id(src) for src, _ in select_sources(s)}
    for src in SOURCES:
        mark = f"{C['ok']}on " if id(src) in active else f"{C['dim']}-- "
        tag = " [bulk]" if src.bulk else ""
        print(f"  {mark}{C['reset']} {src.name:<22} {src.note}{tag}")
    print(f"\n  {C['dim']}sources matching current filters: "
          f"{len(active)}/{len(SOURCES)}{C['reset']}")


def menu_loop(s: Settings) -> None:
    while True:
        print(f"\n{C['dim']}{s.describe()}{C['reset']}")
        print("  [1] Download proxies")
        print("  [2] Protocol")
        print("  [3] Anonymity")
        print("  [4] Country")
        print(f"  [5] Bulk pools      {'(on)' if s.bulk else '(off)'}")
        print("  [6] List sources")
        print("  [0] Exit")
        choice = ask(f"\n{C['head']}>{C['reset']} ")

        if choice == "1":
            run_download(s)
        elif choice == "2":
            set_protocol(s)
        elif choice == "3":
            set_anonymity(s)
        elif choice == "4":
            set_country(s)
        elif choice == "5":
            s.bulk = not s.bulk
        elif choice == "6":
            show_sources(s)
        elif choice in ("0", "q", "quit", "exit"):
            print("bye")
            return
        else:
            print(f"{C['warn']}  unknown option{C['reset']}")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Download free proxies from multiple sources into proxy.txt.")
    ap.add_argument("--protocol", choices=sorted(PROTOCOLS), help="proxy protocol")
    ap.add_argument("--anonymity", choices=sorted(ANONYMITY_LEVELS), help="anonymity level")
    ap.add_argument("--country", help="ISO-2 country code (us, de, kz ...)")
    ap.add_argument("--bulk", action="store_true", help="include huge unchecked pools")
    ap.add_argument("--output", type=Path, help="output file (default: proxy.txt here)")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    colorama_init(autoreset=True)
    banner()

    s = Settings()
    if args.protocol:
        s.protocol = args.protocol
    if args.anonymity:
        s.anonymity = args.anonymity
    if args.country:
        code = args.country.strip().lower()
        if len(code) != 2 or not code.isalpha():
            print(f"{C['err']}[!] --country expects a 2-letter ISO code{C['reset']}")
            return 1
        s.country = code
    if args.bulk:
        s.bulk = True
    if args.output:
        s.output = args.output

    if any([args.protocol, args.anonymity, args.country, args.bulk, args.output]):
        run_download(s)
    else:
        menu_loop(s)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\ninterrupted")
        sys.exit(0)
