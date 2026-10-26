"""Build the ESC site into public/.

Only the paths listed in OWNED are ever written. Everything else in
public/ (teaching/, robots.txt) is left alone.

Run:  uv run build.py
"""
import re
from pathlib import Path

import markdown
import yaml
from jinja2 import Environment, FileSystemLoader

import figures.lab
import figures.legend

ROOT = Path(__file__).parent
CONTENT = ROOT / "content"
PUBLIC = ROOT / "public"
SITE_URL = "https://efficientsystems.ca"

# Model exports this site may use. Each is copied in from its owner's repo when
# that repo sits beside this one; the copy is committed, so the site still
# builds without it. Only published exports are read, never a raw model.
EXPORTS = {
    "house.yaml": ROOT.parent / "house" / "exports" / "public.yaml",
}

# Figures wider than this (in SVG units) break out of the text column, so detailed
# views keep their text at full size instead of shrinking to fit.
WIDE_FIGURE = 800

# The only top-level paths in public/ this script may create or replace.
OWNED = ["index.html", "style.css", "llms.txt", "principles", "legend", "lab"]

env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=True)


def read_page(path):
    """Split a Markdown file into its YAML header and an HTML body.

    If the header names figures, the SVG files next to the page are
    read in so they can be placed inline (each then follows the site's
    light/dark theme and its text stays readable to agents).
    """
    text = path.read_text(encoding="utf-8")
    _, header, body = text.split("---", 2)
    page = yaml.safe_load(header)
    page["body"] = markdown.markdown(body, extensions=["tables"])
    # A page may name one figure (figure + caption) or several (figures: list),
    # or take every SVG in a folder (figures_dir), captioned by file name.
    figs = page.get("figures") or (
        [{"file": page["figure"], "caption": page.get("caption", "")}] if page.get("figure") else []
    )
    if page.get("figures_dir"):
        for svg in sorted((path.parent / page["figures_dir"]).glob("*.svg")):
            figs.append({"file": f"{page['figures_dir']}/{svg.name}", "caption": svg.stem})
    page["figs"] = []
    for f in figs:
        svg = (path.parent / f["file"]).read_text(encoding="utf-8")
        m = re.search(r'viewBox="0 0 ([0-9.]+)', svg)
        wide = bool(m) and float(m.group(1)) > WIDE_FIGURE
        page["figs"].append({"svg": re.sub(r"<\?xml[^>]*\?>\s*", "", svg), "caption": f["caption"], "wide": wide})
    return page


def write(rel, text):
    """Write a file into public/, but only if this script owns that path."""
    if rel.split("/")[0] not in OWNED:
        raise SystemExit(f"Refusing to write public/{rel}: not in OWNED")
    out = PUBLIC / rel
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")


def render(template, rel, page, **extra):
    """Render one page, write it, and return it for the site index."""
    page["url"] = "/" + rel.removesuffix("index.html")
    write(rel, env.get_template(template).render(page=page, **extra))
    return page


def llms_txt(pages):
    """A plain-text index of the site for AI agents (llmstxt.org format)."""
    lines = [
        "# Efficient Systems Canada",
        "",
        "> Working notes on industrial context, operations, and AI transformation.",
        "",
        "## Pages",
        "",
    ]
    for p in pages:
        if p.get("noindex"):
            continue
        lines.append(f"- [{p['title']}]({SITE_URL}{p['url']}): {p['description']}")
    return "\n".join(lines) + "\n"


def sync_exports():
    """Copy each owner's public export into content/models/ if it changed."""
    models = CONTENT / "models"
    models.mkdir(exist_ok=True)
    for name, src in EXPORTS.items():
        dst = models / name
        if not src.exists():
            print(f"Using committed content/models/{name} ({src.parent.parent.name} repo not found)")
            continue
        text = src.read_text(encoding="utf-8")
        if not dst.exists() or dst.read_text(encoding="utf-8") != text:
            dst.write_text(text, encoding="utf-8")
            print(f"Updated content/models/{name} from {src.parent.parent.name}/exports/{src.name}")


def main():
    sync_exports()

    # Figures next: generated SVGs land in content/ and are read in below.
    figures.legend.main()
    figures.lab.main()

    pages = []

    # Single pages
    pages.append(render("page.html", "index.html", read_page(CONTENT / "home.md")))
    pages.append(render("page.html", "legend/index.html", read_page(CONTENT / "legend.md")))
    pages.append(render("page.html", "lab/index.html", read_page(CONTENT / "lab.md")))

    # Principles: one page each, ordered by their number
    principles = []
    for path in sorted((CONTENT / "principles").glob("*.md")):
        p = read_page(path)
        p["slug"] = path.stem
        principles.append(p)
    principles.sort(key=lambda p: p["number"])
    for p in principles:
        pages.append(render("principle.html", f"principles/{p['slug']}/index.html", p))

    index = read_page(CONTENT / "principles.md")
    pages.append(render("principles.html", "principles/index.html", index, principles=principles))

    write("style.css", (ROOT / "static" / "style.css").read_text(encoding="utf-8"))
    write("llms.txt", llms_txt(pages))
    print(f"Built {len(pages)} page(s) into public/")


if __name__ == "__main__":
    main()
