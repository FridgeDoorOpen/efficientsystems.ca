"""Draw a view: lay it out with layout.py, then draw it with the grammar.

    from figures.views import load, draw
    fig = draw(load("figures/examples/sample-historian.yaml"))
    fig.save("content/lab/sample-historian.svg", source="figures/views.py")
"""
from pathlib import Path

import yaml

from figures.grammar import Figure
from figures.layout import layout, section_layout


def load(path):
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def halo_for(bands):
    """Return a function giving the halo classes for text at height y, so the
    outline matches the band behind it and lines can pass under the text."""
    def halo(y):
        i = next((k for k, b in enumerate(bands) if b["y"] <= y < b["y"] + b["h"]), 1)
        return " f-halo f-on-band" if i % 2 == 0 else " f-halo"
    return halo


def draw(view):
    if view["view"].get("kind") == "section":
        return draw_section(view)
    meta = view["view"]
    lay = layout(view)
    fig = Figure(meta["id"], lay.width, lay.height, title=meta["title"])
    halo = halo_for(lay.bands)

    # Frame: bands with their level labels, then column headings.
    for i, b in enumerate(lay.bands):
        fig.band(0, b["y"], lay.width, b["h"], alt=i % 2 == 1)
        fig.band_label(12, b["y"] + 24, b["code"], b["name"])
    for c in lay.columns:
        fig.heading(c["x"] + c["w"] / 2, 26, c["title"], anchor="middle")

    # Lines go under the boxes.
    for r in lay.routes:
        e, pts = r["edge"], r["points"]
        fig.route(pts, kind=e.get("kind", "flow"), planned=e.get("status") == "planned")
        if e.get("label"):
            _edge_label(fig, pts, e["label"], halo)

    # Unobserved things: a short path upward that stops (the legend's "no path").
    # Other nodes may carry a short note centred above the box (e.g. "estimated").
    for n in view["nodes"]:
        if n.get("note"):
            x, y, w, h = lay.boxes[n["id"]]
            fig.text(x + w / 2, y - 7, n["note"], "f-small f-muted" + halo(y - 7), anchor="middle")
        if n.get("no_path") == "up":
            x, y, w, h = lay.boxes[n["id"]]
            cx = x + w / 2
            fig.no_path(cx, y, cx, y - 6)
            fig.text(cx + 14, y - 14, n.get("no_path_note", "no path"), "f-small f-muted" + halo(y - 14))

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


def _edge_label(fig, pts, text, halo):
    """Put a line's label beside its longest segment."""
    segs = list(zip(pts, pts[1:]))
    (ax, ay), (bx, by) = max(segs, key=lambda s: abs(s[1][0] - s[0][0]) + abs(s[1][1] - s[0][1]))
    if abs(ax - bx) < 0.5:   # vertical: to the right of the line
        x, y, anchor = ax + 6, (ay + by) / 2 + 4, None
    else:                    # horizontal: just above the line
        x, y, anchor = (ax + bx) / 2, ay - 6, "middle"
    fig.text(x, y, text, "f-small f-muted" + halo(y), anchor=anchor)


def draw_section(view):
    """A section through a building: floors stacked, rooms as containers,
    devices inside them, and the physical links between devices."""
    meta = view["view"]
    lay = section_layout(view)
    fig = Figure(meta["id"], lay.width, lay.height, title=meta["title"])
    for i, b in enumerate(lay.bands):
        fig.band(0, b["y"], lay.width, b["h"], alt=i % 2 == 1)
        fig.band_label(12, b["y"] + 24, b["code"], b["name"])
    halo = halo_for(lay.bands)

    for r in view["rooms"]:
        x, y, w, h = lay.containers[r["id"]]
        fig.group(x, y, w, h)
        fig.text(x + 10, y + 20, r.get("label", r["id"]), "f-label" + halo(y))

    # Links under the devices.
    for route in lay.routes:
        link, pts = route["edge"], route["points"]
        if route.get("control"):
            fig.curve(pts[0], route["control"], pts[1], kind=link.get("kind", "radio"))
            continue
        fig.route(pts, kind=link.get("kind", "wired"))
        if link.get("tag"):
            _link_tag(fig, pts, link["tag"], halo)

    for d in view.get("devices", []):
        x, y, w, h = lay.boxes[d["id"]]
        fig.asset(x, y, w, h, planned=d.get("status") == "planned")
        fig.text(x + w / 2, y + h / 2 + 4, d.get("label", d["id"]), "f-small", anchor="middle")
        for cx, cy, line in lay.captions[d["id"]]:
            fig.text(cx, cy, line, "f-small f-muted" + halo(cy), anchor="middle")
    return fig


def _link_tag(fig, pts, text, halo):
    """Tag a link (e.g. its medium) beside its longest segment."""
    segs = list(zip(pts, pts[1:]))
    (ax, ay), (bx, by) = max(segs, key=lambda s: abs(s[1][0] - s[0][0]) + abs(s[1][1] - s[0][1]))
    if abs(ax - bx) < 0.5:
        x, y, anchor = ax + 5, (ay + by) / 2 + 3, None
    else:
        x, y, anchor = (ax + bx) / 2, ay - 5, "middle"
    fig.text(x, y, text.upper(), "f-tag" + halo(y), anchor=anchor)
