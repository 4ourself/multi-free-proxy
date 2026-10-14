#!/usr/bin/env python3

import argparse
import random
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

try:
    import requests
except ImportError as exc:
    print(f"error: missing library: {getattr(exc, 'name', None) or exc}")
    print("run start.bat or: python -m pip install -r requirements.txt")
    sys.exit(2)

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
        self.randomize: bool = False
        self.output: Path = DEFAULT_OUTPUT

    def describe(self) -> str:
        return (
            f"protocol={self.protocol or 'all'} | anonymity={self.anonymity or 'all'} "
            f"| country={self.country or 'all'} | bulk={'on' if self.bulk else 'off'} "
            f"| random={'on' if self.randomize else 'off'}"
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
        print("error: no source matches these filters")
        print("relax anonymity/country or enable bulk pools")
        return

    url_count = sum(len(u) for _, u in jobs)
    print(f"{len(jobs)} sources / {url_count} requests")
    print(s.describe())
    print()

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
                print(f"  {label:<30}{'failed (' + type(exc).__name__ + ')':>24}")
                continue
            results[url] = proxies
            raw_total += len(proxies)
            print(f"  {label:<30}{len(proxies):>24,}")

    merged = dict.fromkeys(
        proxy for _, urls in jobs for url in urls for proxy in results.get(url, ())
    )
    proxies = sorted(
        merged,
        key=lambda p: (tuple(int(x) for x in p.split(":")[0].split(".")), int(p.split(":")[1])),
    )

    print()
    if not proxies:
        print("no proxies found, output not written")
        return

    if s.randomize:
        random.shuffle(proxies)

    s.output.write_text("\n".join(proxies) + "\n", encoding="utf-8")
    print(f"unique {len(proxies):,} (raw {raw_total:,}) in {time.time() - t0:.1f}s")
    print(f"saved: {s.output}")

def ask(prompt: str) -> str:
    try:
        return input(prompt).strip().lower()
    except (EOFError, KeyboardInterrupt):
        sys.exit(0)


def pick_option(title: str, options: list[tuple[str | None, str]], current: str | None) -> str | None:
    print(f"\n{title}")
    for i, (_, label) in enumerate(options, 1):
        print(f"  [{i}] {label}")
    choice = ask("> ")
    if not choice:
        return current
    if choice in ("0", "all"):
        return None
    if choice.isdigit() and 1 <= int(choice) <= len(options):
        return options[int(choice) - 1][0]
    for value, label in options:
        if choice == label or (value is not None and choice == value):
            return value
    print("invalid, unchanged")
    return current


def set_protocol(s: Settings) -> None:
    opts = [(p, p) for p in ("http", "https", "socks4", "socks5")] + [(None, "all")]
    s.protocol = pick_option("protocol:", opts, s.protocol)


def set_anonymity(s: Settings) -> None:
    opts = [(a, a) for a in ("elite", "anonymous", "transparent")] + [(None, "all")]
    s.anonymity = pick_option("anonymity:", opts, s.anonymity)


def set_country(s: Settings) -> None:
    print("\ncountry (ISO-2 code, 'all' for everything):")
    code = ask("> ")
    if not code:
        return
    if code in ("all", "0"):
        s.country = None
    elif len(code) == 2 and code.isalpha():
        s.country = code
    else:
        print("invalid, unchanged")


def show_sources(s: Settings) -> None:
    active = {id(src) for src, _ in select_sources(s)}
    print()
    for src in SOURCES:
        mark = "on " if id(src) in active else "off"
        print(f"  {mark}  {src.name:<22}{src.note}")
    print(f"\nsources matching filters: {len(active)}/{len(SOURCES)}")


def menu_loop(s: Settings) -> None:
    aliases = {
        "download": "1", "protocol": "2", "anonymity": "3", "country": "4",
        "bulk": "5", "randomize": "6", "random": "6", "sources": "7",
    }
    while True:
        print(f"\n{s.describe()}")
        print("  [1] download")
        print("  [2] protocol")
        print("  [3] anonymity")
        print("  [4] country")
        print(f"  [5] bulk pools ({'on' if s.bulk else 'off'})")
        print(f"  [6] randomize ({'on' if s.randomize else 'off'})")
        print("  [7] sources")
        print("  [0] exit")
        choice = ask("> ")
        choice = aliases.get(choice, choice)

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
            s.randomize = not s.randomize
        elif choice == "7":
            show_sources(s)
        elif choice in ("0", "q", "quit", "exit"):
            return
        else:
            print("invalid, unchanged")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Download free proxies from multiple sources into proxy.txt.")
    ap.add_argument("--protocol", choices=sorted(PROTOCOLS), help="proxy protocol")
    ap.add_argument("--anonymity", choices=sorted(ANONYMITY_LEVELS), help="anonymity level")
    ap.add_argument("--country", help="ISO-2 country code (us, de, kz ...)")
    ap.add_argument("--bulk", action="store_true", help="include huge unchecked pools")
    ap.add_argument("--random", action="store_true", help="randomize output order")
    ap.add_argument("--output", type=Path, help="output file (default: proxy.txt here)")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    s = Settings()
    if args.protocol:
        s.protocol = args.protocol
    if args.anonymity:
        s.anonymity = args.anonymity
    if args.country:
        code = args.country.strip().lower()
        if len(code) != 2 or not code.isalpha():
            print("error: --country expects a 2-letter ISO code")
            return 1
        s.country = code
    if args.bulk:
        s.bulk = True
    if args.random:
        s.randomize = True
    if args.output:
        s.output = args.output

    if any([args.protocol, args.anonymity, args.country, args.bulk, args.random, args.output]):
        run_download(s)
    else:
        menu_loop(s)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(1)
