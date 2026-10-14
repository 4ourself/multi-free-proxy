"""
make_screenshots.py - regenerate the README terminal screenshots.

Runs main.py, feeds its output through the pyte terminal emulator and
renders the resulting screen to PNG with Pillow.

    python tools/make_screenshots.py
"""

from __future__ import annotations

import os
import pty
import re
import select
import subprocess
import sys
from pathlib import Path

import pyte
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "images"
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FONT_BOLD_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"

COLS, ROWS = 80, 32
FONT_SIZE = 15
PAD = 18

BG = (12, 12, 12)
FG_DEFAULT = (220, 220, 220)
COLORS = {
    "default": FG_DEFAULT,
    "black": (12, 12, 12), "red": (205, 49, 49), "green": (13, 188, 121),
    "brown": (229, 229, 16), "yellow": (229, 229, 16), "blue": (36, 114, 200),
    "magenta": (188, 63, 188), "cyan": (17, 168, 205), "white": (229, 229, 229),
    "brightblack": (102, 102, 102), "brightred": (241, 76, 76),
    "brightgreen": (35, 209, 139), "brightbrown": (245, 245, 67),
    "brightyellow": (245, 245, 67), "brightblue": (59, 142, 234),
    "brightmagenta": (214, 112, 214), "brightcyan": (41, 184, 219),
    "brightwhite": (229, 229, 229),
}


def run_in_pty(argv: list[str], stdin_text: str) -> str:
    """Run a command on a real pty so colorama keeps its ANSI colors."""
    master, slave = pty.openpty()
    proc = subprocess.Popen(
        argv, stdin=slave, stdout=slave, stderr=slave, cwd=ROOT,
        env={**os.environ, "TERM": "xterm-256color"},
    )
    os.close(slave)
    if stdin_text:
        os.write(master, stdin_text.encode())
    out = b""
    while True:
        ready, _, _ = select.select([master], [], [], 15)
        if not ready:
            break
        try:
            chunk = os.read(master, 65536)
        except OSError:  # child exited (Linux raises EIO on the master)
            break
        if not chunk:
            break
        out += chunk
    proc.wait()
    os.close(master)
    return out.decode(errors="replace").replace("\r\n", "\n")


def capture(
    argv: list[str],
    stdin: str = "",
    strip_leading: str = "",
    strip_trailing_re: str = "",
) -> pyte.Screen:
    """Run main.py in a pty and replay its output through pyte."""
    out = run_in_pty([sys.executable, "main.py", *argv], stdin)
    if strip_leading and out.startswith(strip_leading):
        out = out[len(strip_leading):]  # the pty echoes typed input immediately
    if strip_trailing_re:
        out = re.sub(strip_trailing_re, "", out)
    # a real TTY converts "\n" to "\r\n" (ONLCR); pyte needs the "\r"
    out = out.replace("\n", "\r\n")
    screen = pyte.Screen(COLS, ROWS)
    stream = pyte.Stream(screen)
    cmd = "python main.py" + (" " + " ".join(argv) if argv else "")
    stream.feed(f"\x1b[90m$ \x1b[0m\x1b[1m{cmd}\x1b[0m\r\n")
    stream.feed(out)
    return screen


def render(screen: pyte.Screen, path: Path, cursor: tuple[int, int] | None = None) -> None:
    font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
    font_bold = ImageFont.truetype(FONT_BOLD_PATH, FONT_SIZE)
    cell_w = round(font.getlength("M"))
    ascent, descent = font.getmetrics()
    cell_h = ascent + descent

    # find last visible row so the image isn't full of empty lines
    last = 0
    for y in range(ROWS):
        for x in range(COLS):
            if screen.buffer[y][x].data.strip():
                last = y
                break
    if cursor:
        last = max(last, cursor[1])

    w = COLS * cell_w + PAD * 2
    h = (last + 1) * cell_h + PAD * 2
    img = Image.new("RGB", (w, h), BG)
    draw = ImageDraw.Draw(img)

    for y in range(last + 1):
        for x in range(COLS):
            cell = screen.buffer[y][x]
            ch = cell.data
            if not ch or ch == " ":
                continue
            color = COLORS.get(cell.fg, FG_DEFAULT)
            f = font_bold if cell.bold else font
            draw.text((PAD + x * cell_w, PAD + y * cell_h), ch, font=f, fill=color)

    if cursor:
        cx, cy = cursor
        draw.rectangle(
            [PAD + cx * cell_w, PAD + cy * cell_h + 2,
             PAD + cx * cell_w + cell_w - 2, PAD + cy * cell_h + cell_h - 4],
            fill=FG_DEFAULT,
        )

    img.save(path)
    print(f"saved {path}  ({w}x{h})")


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)

    # 1) main menu, waiting for input
    #    drop the echoed "0" at the start and the "bye" at the end
    #    (colorama autoreset may sneak \x1b[0m sequences in between)
    menu = capture(
        [], stdin="0\n",
        strip_leading="0\n",
        strip_trailing_re=r"bye(?:\x1b\[[0-9;]*m|\s)*$",
    )
    # cursor right after the "> " prompt at the bottom
    cursor = None
    for y in range(ROWS - 1, -1, -1):
        row = "".join(menu.buffer[y][x].data for x in range(COLS)).rstrip()
        if row.endswith(">"):
            cursor = (len(row) + 1, y)
            break
    render(menu, OUT_DIR / "menu.png", cursor=cursor)

    # 2) a real download run
    download = capture(["--protocol", "http"])
    render(download, OUT_DIR / "download.png")


if __name__ == "__main__":
    main()
