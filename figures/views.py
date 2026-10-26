"""Draw a view: lay it out with layout.py, then draw it with the grammar.

    from figures.views import load, draw
    fig = draw(load("figures/examples/sample-historian.yaml"))
    fig.save("content/lab/sample-historian.svg", source="figures/views.py")
"""
from pathlib import Path

import yaml

from figures.grammar import Figure
from figures.layout import layout


def load(path):
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def draw(view):
    meta = view["view"]
    lay = layout(view)
    fig = Figure(meta["id"], lay.width, lay.height, title=meta["title"])

    # Frame: bands with their level labels, then column headings.
    for i, b in enumerate(lay.bands):
        fig.band(0, b["y"], lay.width, b["h"], alt=i % 2 == 1)
        fig.band_label(12, b["y"] + 24, b["code"], b["name"])
    for c in lay.columns:
        fig.heading(c["x"] + c["w"] / 2, 26, c["title"], anchor="middle")

    # Lines go under the boxes.
    for r in lay.routes:
        e, pts = r["edge"], r["points"]
        fig.route(pts, kind=e.get("kind", "flow"))
        if e.get("label"):
            _edge_label(fig, pts, e["label"])

    # Boxes and their labels.
    for n in view["nodes"]:
        x, y, w, h = lay.boxes[n["id"]]
        kind = n.get("kind", "system")
        planned = n.get("status") == "planned"
        label = n.get("label", n["id"])
        if kind == "role":
            fig.role(x, y + h / 2 - 12, 24, 24, planned=planned)
            fig.label(x + 32, y + h / 2 + 4.5, label)
        elif kind == "decision":
            fig.decision(x, y, 30, h, planned=planned)
            fig.label(x + 38, y + h / 2 + 4.5, label)
        else:
            getattr(fig, kind)(x, y, w, h, planned=planned)
            fig.label(x + w / 2, y + h / 2 + 4.5, label, anchor="middle")
    return fig


def _edge_label(fig, pts, text):
    """Put a line's label beside its longest segment."""
    segs = list(zip(pts, pts[1:]))
    (ax, ay), (bx, by) = max(segs, key=lambda s: abs(s[1][0] - s[0][0]) + abs(s[1][1] - s[0][1]))
    if abs(ax - bx) < 0.5:   # vertical: to the right of the line
        fig.note(ax + 6, (ay + by) / 2 + 4, text)
    else:                    # horizontal: just above the line
        fig.note((ax + bx) / 2, ay - 6, text, anchor="middle")
