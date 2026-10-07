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

ROOT = Path(__file__).parent
CONTENT = ROOT / "content"
PUBLIC = ROOT / "public"
SITE_URL = "https://efficientsystems.ca"

# The only top-level paths in public/ this script may create or replace.
OWNED = ["index.html", "style.css", "llms.txt", "principles", "legend"]

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
    # A page may name one figure (figure + caption) or several (figures: list).
    figs = page.get("figures") or (
        [{"file": page["figure"], "caption": page.get("caption", "")}] if page.get("figure") else []
    )
    page["figs"] = []
    for f in figs:
        svg = (path.parent / f["file"]).read_text(encoding="utf-8")
        page["figs"].append({"svg": re.sub(r"<\?xml[^>]*\?>\s*", "", svg), "caption": f["caption"]})
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
        lines.append(f"- [{p['title']}]({SITE_URL}{p['url']}): {p['description']}")
    return "\n".join(lines) + "\n"


def main():
    pages = []

    # Single pages
    pages.append(render("page.html", "index.html", read_page(CONTENT / "home.md")))
    pages.append(render("page.html", "legend/index.html", read_page(CONTENT / "legend.md")))

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
