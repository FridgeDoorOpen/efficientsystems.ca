"""The visual grammar as code: one method per shape and line in the legend.

Every figure on the site is drawn from the same small set of parts, so this
module is the single place those parts are defined. Colours are never set
here; each element only gets an `f-` class, and static/style.css decides how
it looks in light and dark themes.

Conventions
-----------
- Every shape takes a box: (x, y, w, h). Circles, diamonds and chevrons are
  drawn to fit inside their box, so a layout engine can place any kind of
  node the same way.
- Every figure has an id prefix (e.g. "lg"). Inline SVGs on one page share an
  id namespace, so marker ids are prefixed to keep figures from clashing.
- Every figure needs a title: a sentence stating what it shows, readable by
  people using screen readers and by AI agents.

Example
-------
    fig = Figure("lg", 720, 476, title="Legend: ...")
    fig.asset(20, 48, 72, 34)
    fig.label(110, 62, "Asset")
    fig.line(390, 65, 462, 65, kind="flow")
    fig.save(path, source="figures/legend.py")
"""
import copy
import math
import xml.etree.ElementTree as ET
from pathlib import Path

# Line kinds from the legend: (CSS class, arrowhead marker or None).
LINE_KINDS = {
    "flow": ("f-flow", "arrow"),                 # documented data flow
    "inferred": ("f-flow f-inferred", "arrow"),  # believed, not documented
    "human": ("f-flow-human", None),             # carried by people
    "tie": ("f-tie", None),                      # association: belongs to, describes
    "accent": ("f-accent-flow", "arrow-accent"), # the point of the figure
}

# Arrowhead markers, added to <defs> only when a line uses them.
MARKERS = {
    "arrow": "f-arrowhead",
    "arrow-accent": "f-arrowhead-accent",
}


def num(v):
    """Format a coordinate: whole numbers without decimals, others to 1 place."""
    v = round(float(v), 1)
    return str(int(v)) if v == int(v) else f"{v:.1f}"


class Figure:
    def __init__(self, prefix, width, height, title):
        if not title or not title.strip():
            raise ValueError("Every figure needs a title stating what it shows.")
        self.prefix = prefix
        self.root = ET.Element("svg", {
            "class": "fig",
            "viewBox": f"0 0 {num(width)} {num(height)}",
            "role": "img",
            "aria-labelledby": f"{prefix}-title",
            "xmlns": "http://www.w3.org/2000/svg",
        })
        ET.SubElement(self.root, "title", {"id": f"{prefix}-title"}).text = title.strip()
        self.defs = None
        self.markers = set()

    # ---- internals ----------------------------------------------------------

    def _add(self, tag, cls, **attrs):
        el = ET.SubElement(self.root, tag, {"class": cls} if cls else {})
        for k, v in attrs.items():
            el.set(k.replace("_", "-"), num(v) if isinstance(v, (int, float)) else str(v))
        return el

    def _marker(self, name):
        """Return the url() for a marker, adding it to <defs> on first use."""
        mid = f"{self.prefix}-{name}"
        if name not in self.markers:
            if self.defs is None:
                self.defs = ET.Element("defs")
                self.root.insert(1, self.defs)  # straight after <title>
            m = ET.SubElement(self.defs, "marker", {
                "id": mid, "viewBox": "0 0 10 10", "refX": "9", "refY": "5",
                "markerWidth": "7", "markerHeight": "7", "orient": "auto-start-reverse",
            })
            ET.SubElement(m, "path", {"d": "M0 0L10 5L0 10z", "class": MARKERS[name]})
            self.markers.add(name)
        return f"url(#{mid})"

    # ---- things (shapes) ----------------------------------------------------
    # Every shape takes planned=True to draw it with a dashed outline:
    # something decided on but not built yet.

    @staticmethod
    def _cls(base, planned):
        return f"{base} f-planned" if planned else base

    def asset(self, x, y, w, h, planned=False):
        """Physical equipment. Square corners, filled."""
        return self._add("rect", self._cls("f-asset", planned), x=x, y=y, width=w, height=h)

    def system(self, x, y, w, h, planned=False):
        """Software or platform. Rounded, open."""
        return self._add("rect", self._cls("f-system", planned), x=x, y=y, width=w, height=h, rx=8)

    def role(self, x, y, w, h, planned=False):
        """A person or team, by role. A circle centred in its box."""
        return self._add("circle", self._cls("f-role", planned), cx=x + w / 2, cy=y + h / 2, r=min(w, h) / 2)

    def process(self, x, y, w, h, planned=False):
        """How work moves. A chevron: notched on the left, pointed on the right."""
        p = min(14, w / 4)
        d = (f"M{num(x)} {num(y)}H{num(x + w - p)}L{num(x + w)} {num(y + h / 2)}"
             f"L{num(x + w - p)} {num(y + h)}H{num(x)}L{num(x + p)} {num(y + h / 2)}Z")
        return self._add("path", self._cls("f-process", planned), d=d)

    def decision(self, x, y, w, h, planned=False):
        """A judgment someone actually makes. A diamond filling its box."""
        cx, cy = x + w / 2, y + h / 2
        d = (f"M{num(cx)} {num(y)}L{num(x + w)} {num(cy)}"
             f"L{num(cx)} {num(y + h)}L{num(x)} {num(cy)}Z")
        return self._add("path", self._cls("f-decision", planned), d=d)

    def artifact(self, x, y, w, h, planned=False):
        """A form, template, rating or document. A page with a folded corner."""
        f = min(12, w / 4, h / 2)
        self._add("path", self._cls("f-artifact", planned),
                  d=f"M{num(x)} {num(y)}H{num(x + w - f)}L{num(x + w)} {num(y + f)}"
                    f"V{num(y + h)}H{num(x)}Z")
        return self._add("path", "f-artifact-fold",
                         d=f"M{num(x + w - f)} {num(y)}V{num(y + f)}H{num(x + w)}")

    def group(self, x, y, w, h, planned=False):
        """Things read together as one."""
        return self._add("rect", self._cls("f-group", planned), x=x, y=y, width=w, height=h, rx=6)

    # ---- lines --------------------------------------------------------------

    def line(self, x1, y1, x2, y2, kind="flow"):
        """A straight line of one of the legend's kinds (see LINE_KINDS)."""
        if kind not in LINE_KINDS:
            raise ValueError(f"Unknown line kind {kind!r}; use one of {list(LINE_KINDS)}")
        cls, marker = LINE_KINDS[kind]
        if kind == "human":
            # Drawn as a path so the style can give it its doubled look.
            return self._add("path", cls, d=f"M{num(x1)} {num(y1)}L{num(x2)} {num(y2)}")
        el = self._add("line", cls, x1=x1, y1=y1, x2=x2, y2=y2)
        if marker:
            el.set("marker-end", self._marker(marker))
        return el

    def no_path(self, x1, y1, x2, y2):
        """Where a flow should continue, and doesn't: a line ending in a break mark."""
        self._add("line", "f-flow", x1=x1, y1=y1, x2=x2, y2=y2)
        return self._break(x1, y1, x2, y2)

    def route(self, points, kind="flow"):
        """A line through several points (e.g. with elbows), of any line kind,
        or "no_path" to stop short of the last point with a break mark."""
        pts = [(float(x), float(y)) for x, y in points]
        if kind == "no_path":
            (ax, ay), (bx, by) = pts[-2], pts[-1]
            seg = math.hypot(bx - ax, by - ay) or 1
            cut = min(26, seg * 0.6)                        # leave room for the break
            pts[-1] = (bx - (bx - ax) / seg * cut, by - (by - ay) / seg * cut)
            self._add("path", "f-flow", d=self._d(pts))
            return self._break(*pts[-2], *pts[-1])
        if kind not in LINE_KINDS:
            raise ValueError(f"Unknown line kind {kind!r}; use one of {list(LINE_KINDS)} or 'no_path'")
        cls, marker = LINE_KINDS[kind]
        el = self._add("path", cls, d=self._d(pts))
        if marker:
            el.set("marker-end", self._marker(marker))
        return el

    @staticmethod
    def _d(pts):
        return "M" + "L".join(f"{num(x)} {num(y)}" for x, y in pts)

    def _break(self, x1, y1, x2, y2):
        """Two slashes just past (x2, y2), across the direction of travel."""
        length = math.hypot(x2 - x1, y2 - y1) or 1
        dx, dy = (x2 - x1) / length, (y2 - y1) / length   # along the line
        nx, ny = dy, -dx                                    # across it
        parts = []
        for offset in (9, 19):                              # two slashes past the end
            sx, sy = x2 + dx * offset, y2 + dy * offset
            ax, ay = sx - 5 * dx - 8 * nx, sy - 5 * dy - 8 * ny
            bx, by = sx + 5 * dx + 8 * nx, sy + 5 * dy + 8 * ny
            parts.append(f"M{num(ax)} {num(ay)}L{num(bx)} {num(by)}")
        return self._add("path", "f-break", d="".join(parts))

    # ---- frames -------------------------------------------------------------

    def band(self, x, y, w, h, alt=False):
        """One ISA-95 level band. Alternate bands with alt=True."""
        return self._add("rect", "f-band-alt" if alt else "f-band", x=x, y=y, width=w, height=h)

    def band_label(self, x, y, code, name):
        """The level code and name at the left edge of a band, e.g. L3 / Operations."""
        g = ET.SubElement(self.root, "g", {"class": "f-band-label"})
        ET.SubElement(g, "text", {"x": num(x), "y": num(y)}).text = code
        if name:
            ET.SubElement(g, "text", {"class": "f-small", "x": num(x), "y": num(y + 16)}).text = name
        return g

    def grid(self, x, y, w, h, rows, cols, fill=None):
        """A RAMI 4.0 style grid of cells. `fill(row, col)` may return an
        ownership class (e.g. "f-own-ops"); the default is "f-own-none"."""
        cw, ch = w / cols, h / rows
        for r in range(rows):
            for c in range(cols):
                own = (fill(r, c) if fill else None) or "f-own-none"
                self._add("rect", f"f-cell {own}", x=x + c * cw, y=y + r * ch, width=cw, height=ch)

    # ---- text ---------------------------------------------------------------

    def text(self, x, y, s, cls="f-label", anchor=None):
        el = self._add("text", cls, x=x, y=y, **({"text_anchor": anchor} if anchor else {}))
        el.text = s
        return el

    def heading(self, x, y, s, anchor=None):
        return self.text(x, y, s, "f-heading", anchor)

    def label(self, x, y, s, anchor=None):
        return self.text(x, y, s, "f-label", anchor)

    def note(self, x, y, s, anchor=None):
        """Small, muted explanatory text."""
        return self.text(x, y, s, "f-small f-muted", anchor)

    def accent_text(self, x, y, s, anchor=None):
        """Text that carries the point of the figure."""
        return self.text(x, y, s, "f-accent-text", anchor)

    # ---- output -------------------------------------------------------------

    def to_string(self, source=None):
        root = self.root
        if source:
            root = copy.deepcopy(self.root)
            root.insert(0, ET.Comment(f" Generated by {source}. Do not edit by hand. "))
        ET.indent(root, "  ")
        return ET.tostring(root, encoding="unicode") + "\n"

    def save(self, path, source=None):
        Path(path).write_text(self.to_string(source), encoding="utf-8")
        return path
