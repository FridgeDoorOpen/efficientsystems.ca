"""Build the household views into private/: the full house, for Jay and Shreya only.

Run through the site build:  uv run build.py --household

Reads ../house/exports/household.yaml in place. It is never copied into this repo,
and everything it produces goes into private/, which is git-ignored and outside the
public/ folder that Nginx serves. Nothing here can reach GitHub or the internet.
"""
import re
from datetime import datetime
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader

from figures.adapters import house
from figures.views import draw

ROOT = Path(__file__).parent
EXPORT = ROOT.parent / "house" / "exports" / "household.yaml"
PRIVATE = ROOT / "private"
WIDE_FIGURE = 800

HEADINGS = {"section": "Where everything is", "logical": "What everything does"}


def write(rel, text):
    """Write a file into private/, and nowhere else."""
    out = (PRIVATE / rel).resolve()
    if PRIVATE.resolve() not in out.parents:
        raise SystemExit(f"Refusing to write {out}: outside private/")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")


def main():
    if not EXPORT.exists():
        raise SystemExit(f"No household export at {EXPORT}. Run `uv run exports/export.py household` in the house repo.")
    data = yaml.safe_load(EXPORT.read_text(encoding="utf-8"))

    figs = []
    for make in house.VIEWS:
        svg = draw(make(data)).to_string()                  # in memory only; never saved to content/
        m = re.search(r'viewBox="0 0 ([0-9.]+)', svg)
        figs.append({"heading": HEADINGS.get(make.__name__, make.__name__), "svg": svg,
                     "caption": "", "wide": bool(m) and float(m.group(1)) > WIDE_FIGURE})

    env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=True)
    built = datetime.now().strftime("%Y-%m-%d %H:%M")
    write("index.html", env.get_template("private.html").render(figs=figs, built=built))
    write("style.css", (ROOT / "static" / "style.css").read_text(encoding="utf-8"))
    print(f"Built {len(figs)} household view(s) into private/")
