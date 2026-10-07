"""Build the ESC site into public/.

Only the paths listed in OWNED are ever written. Everything else in
public/ (teaching/, robots.txt) is left alone.

Run:  uv run build.py
"""
from pathlib import Path

import markdown
import yaml
from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).parent
CONTENT = ROOT / "content"
PUBLIC = ROOT / "public"
SITE_URL = "https://efficientsystems.ca"

# The only top-level paths in public/ this script may create or replace.
OWNED = ["index.html", "style.css", "llms.txt"]

# Source page (in content/)  ->  output path (in public/)
PAGES = [
    ("home.md", "index.html"),
]

env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=True)


def read_page(path):
    """Split a Markdown file into its YAML header and an HTML body."""
    text = path.read_text(encoding="utf-8")
    _, header, body = text.split("---", 2)
    page = yaml.safe_load(header)
    page["body"] = markdown.markdown(body, extensions=["tables"])
    return page


def write(rel, text):
    """Write a file into public/, but only if this script owns that path."""
    if rel.split("/")[0] not in OWNED:
        raise SystemExit(f"Refusing to write public/{rel}: not in OWNED")
    out = PUBLIC / rel
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")


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
    template = env.get_template("page.html")
    pages = []
    for src, rel in PAGES:
        page = read_page(CONTENT / src)
        page["url"] = "/" + rel.removesuffix("index.html")
        write(rel, template.render(page=page))
        pages.append(page)

    write("style.css", (ROOT / "static" / "style.css").read_text(encoding="utf-8"))
    write("llms.txt", llms_txt(pages))
    print(f"Built {len(pages)} page(s) into public/")


if __name__ == "__main__":
    main()
