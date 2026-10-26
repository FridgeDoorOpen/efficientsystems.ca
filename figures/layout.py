"""Where everything in a view goes: positions only, no drawing.

A view is plain data (see figures/examples/). This module turns it into
numbers: the y and height of each band, the x and width of each column, a
box for every node, and a list of points for every edge. views.py then draws
those numbers with the grammar.

Rules
-----
- Rows are a fixed frame (ISA-95 levels, top to bottom from L4 to L0). Every
  level is drawn even when empty, because an empty level is information.
- Columns are named by each view, left to right in the order given.
- Nodes in the same cell sit side by side, in the order they are listed.
  A column is as wide as its fullest cell; a band is as tall as one node
  plus padding (empty bands are shorter).
- Box widths are estimated from label length (about 7 px per character),
  since Python can't measure fonts.
- Lines between rows leave the top or bottom of a box and enter the other
  box from the opposite side. If the boxes are in different columns, the line
  takes one elbow at the edge of the target's band. Lines within a row run
  side to side. Where several lines meet one side of a box, their attachment
  points are spread along that side.
"""
from dataclasses import dataclass, field

# Row frames: (code, name), top to bottom.
ROW_FRAMES = {
    "isa95": [
        ("L4", "Business"),
        ("L3", "Operations"),
        ("L2", "Supervisory"),
        ("L1", "Sensing and control"),
        ("L0", "Physical"),
    ],
}

NODE_KINDS = {"asset", "system", "role", "process", "decision", "artifact", "group"}
EDGE_KINDS = {"flow", "inferred", "human", "tie", "accent", "no_path"}

# Dimensions (SVG units, roughly pixels)
GUTTER = 160        # left margin for band labels (fits "Sensing and control")
MARGIN = 20         # right and bottom margin
HEADER = 40         # top margin for column headings
NODE_H = 34
NODE_GAP = 32       # between nodes in one cell (room for an arrow)
CELL_PAD = 24       # left and right inside each column
BAND_PAD = 24       # above and below nodes in a band
EMPTY_BAND = 48     # height of a band with no nodes
MIN_COL = 140
CHAR_W = 7.2        # estimated width of one label character at 13px
LABEL_PAD = 24      # text inset inside a box


@dataclass
class Layout:
    width: float
    height: float
    bands: list = field(default_factory=list)    # dicts: code, name, y, h
    columns: list = field(default_factory=list)  # dicts: id, title, x, w
    boxes: dict = field(default_factory=dict)    # node id -> (x, y, w, h)
    routes: list = field(default_factory=list)   # dicts: edge, points


def node_width(node):
    text = len(node.get("label", node["id"])) * CHAR_W
    if node.get("kind") in ("role", "decision"):
        return 30 + 8 + text      # small mark with the label beside it
    return max(72, text + LABEL_PAD)


def validate(view):
    """Fail loudly on anything the layout can't place, naming the culprit."""
    meta = view["view"]
    if not meta.get("title", "").strip():
        raise ValueError(f"View {meta.get('id')!r} needs a title stating what it shows.")
    rows = {code for code, _ in ROW_FRAMES[meta.get("rows", "isa95")]}
    cols = {c["id"] if isinstance(c, dict) else c for c in meta["columns"]}
    ids = set()
    for n in view["nodes"]:
        where = f"node {n.get('id')!r}"
        if n["id"] in ids:
            raise ValueError(f"Duplicate {where}")
        ids.add(n["id"])
        if n.get("kind", "system") not in NODE_KINDS:
            raise ValueError(f"{where}: unknown kind {n.get('kind')!r}")
        if n["row"] not in rows:
            raise ValueError(f"{where}: unknown row {n['row']!r} (expected one of {sorted(rows)})")
        if n["col"] not in cols:
            raise ValueError(f"{where}: unknown column {n['col']!r} (expected one of {sorted(cols)})")
    for e in view.get("edges", []):
        for end in ("from", "to"):
            if e[end] not in ids:
                raise ValueError(f"Edge {e['from']} → {e['to']}: no node {e[end]!r}")
        if e.get("kind", "flow") not in EDGE_KINDS:
            raise ValueError(f"Edge {e['from']} → {e['to']}: unknown kind {e.get('kind')!r}")


def layout(view):
    validate(view)
    meta = view["view"]
    frame = ROW_FRAMES[meta.get("rows", "isa95")]
    columns = [c if isinstance(c, dict) else {"id": c, "title": c} for c in meta["columns"]]
    nodes = view["nodes"]
    edges = view.get("edges", [])

    # Group nodes into cells, keeping the order they were listed in.
    cells = {}
    for n in nodes:
        cells.setdefault((n["row"], n["col"]), []).append(n)

    def cell_width(row, col):
        ns = cells.get((row, col), [])
        return sum(node_width(n) for n in ns) + NODE_GAP * max(0, len(ns) - 1)

    out = Layout(width=0, height=0)

    # Columns: as wide as the fullest cell.
    x = GUTTER
    for c in columns:
        w = max(MIN_COL, max(cell_width(code, c["id"]) for code, _ in frame) + 2 * CELL_PAD)
        out.columns.append({"id": c["id"], "title": c.get("title", c["id"]), "x": x, "w": w})
        x += w
    out.width = x + MARGIN
    col_at = {c["id"]: c for c in out.columns}

    # Bands: one per level, shorter when empty.
    y = HEADER
    for code, name in frame:
        used = any(r == code for r, _ in cells)
        h = NODE_H + 2 * BAND_PAD if used else EMPTY_BAND
        out.bands.append({"code": code, "name": name, "y": y, "h": h})
        y += h
    out.height = y + MARGIN
    band_at = {b["code"]: b for b in out.bands}
    row_index = {code: i for i, (code, _) in enumerate(frame)}

    # Boxes: centred in their cell, side by side.
    for (row, col), ns in cells.items():
        c, b = col_at[col], band_at[row]
        bx = c["x"] + (c["w"] - cell_width(row, col)) / 2
        by = b["y"] + (b["h"] - NODE_H) / 2
        for n in ns:
            w = node_width(n)
            out.boxes[n["id"]] = (bx, by, w, NODE_H)
            bx += w + NODE_GAP

    # Which side of each box every edge uses.
    by_id = {n["id"]: n for n in nodes}
    sides = {}   # (node id, side) -> list of (edge index, "src"/"dst", other centre)
    plan = []
    for i, e in enumerate(edges):
        s, t = by_id[e["from"]], by_id[e["to"]]
        sx, sy, sw, sh = out.boxes[s["id"]]
        tx, ty, tw, th = out.boxes[t["id"]]
        if s["row"] != t["row"]:
            up = row_index[t["row"]] < row_index[s["row"]]
            s_side, t_side = ("top", "bottom") if up else ("bottom", "top")
            s_other, t_other = tx + tw / 2, sx + sw / 2
        else:
            right = tx > sx
            s_side, t_side = ("right", "left") if right else ("left", "right")
            s_other, t_other = ty + th / 2, sy + sh / 2
        sides.setdefault((s["id"], s_side), []).append((i, "src", s_other))
        sides.setdefault((t["id"], t_side), []).append((i, "dst", t_other))
        plan.append((s_side, t_side))

    # Spread attachment points along each side, ordered by where the other end is.
    ports = {}
    for (nid, side), uses in sides.items():
        bx, by, bw, bh = out.boxes[nid]
        uses.sort(key=lambda u: u[2])
        for k, (i, end, _) in enumerate(uses):
            f = (k + 1) / (len(uses) + 1)
            if side in ("top", "bottom"):
                pt = (bx + bw * f, by if side == "top" else by + bh)
            else:
                pt = (bx if side == "left" else bx + bw, by + bh * f)
            ports[(i, end)] = pt

    # Routes: straight when aligned, otherwise one elbow.
    for i, e in enumerate(edges):
        (px, py), (qx, qy) = ports[(i, "src")], ports[(i, "dst")]
        s_side, _ = plan[i]
        if s_side in ("top", "bottom"):
            if abs(px - qx) < 0.5:
                pts = [(px, py), (qx, qy)]
            else:
                tb = band_at[by_id[e["to"]]["row"]]
                ey = tb["y"] + tb["h"] if s_side == "top" else tb["y"]
                pts = [(px, py), (px, ey), (qx, ey), (qx, qy)]
        else:
            if abs(py - qy) < 0.5:
                pts = [(px, py), (qx, qy)]
            else:
                mx = (px + qx) / 2
                pts = [(px, py), (mx, py), (mx, qy), (qx, qy)]
        out.routes.append({"edge": e, "points": pts})

    return out


# ---- Section views: floors as rows, rooms as containers ----------------------
#
# A section view is a different kind of view:
#
#   view:   {id, title, kind: section}
#   floors: [{id, title}]                  top to bottom
#   rooms:  [{id, label, floor}]           left to right within each floor
#
# Each floor lays out its own rooms independently (floors don't share columns).
# Rooms are sized to fit their label for now; devices placed inside them come next.

SECTION_GUTTER = 120   # left margin for floor names
ROOM_H = 96            # tall enough to hold a row of devices later
ROOM_GAP = 12
ROOM_MIN_W = 124
ROOM_PAD = 20          # inside a floor band, above and below the rooms


def section_layout(view):
    meta = view["view"]
    if not meta.get("title", "").strip():
        raise ValueError(f"View {meta.get('id')!r} needs a title stating what it shows.")
    floor_ids = [f["id"] for f in view["floors"]]
    rooms_by_floor = {fid: [] for fid in floor_ids}
    seen = set()
    for r in view["rooms"]:
        if r["id"] in seen:
            raise ValueError(f"Duplicate room {r['id']!r}")
        seen.add(r["id"])
        if r["floor"] not in rooms_by_floor:
            raise ValueError(f"Room {r['id']!r}: unknown floor {r['floor']!r} (expected one of {floor_ids})")
        rooms_by_floor[r["floor"]].append(r)

    out = Layout(width=0, height=0)
    out.containers = {}
    y, widest = MARGIN, 0
    for f in view["floors"]:
        h = ROOM_H + 2 * ROOM_PAD
        out.bands.append({"code": f["title"], "name": "", "y": y, "h": h})
        x = SECTION_GUTTER
        for r in rooms_by_floor[f["id"]]:
            w = max(ROOM_MIN_W, len(r.get("label", r["id"])) * CHAR_W + LABEL_PAD)
            out.containers[r["id"]] = (x, y + ROOM_PAD, w, ROOM_H)
            x += w + ROOM_GAP
        widest = max(widest, x - ROOM_GAP)
        y += h
    out.width = widest + MARGIN
    out.height = y + MARGIN
    return out
