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
  A cell wider than CELL_MAX_W wraps onto further lines within its band,
  and a node with `break_before: true` always starts a new line. A column
  is as wide as its widest line; a band is as tall as its most-wrapped cell
  (empty bands are shorter). Lines going up should start from the top line
  of a cell, so adapters list those nodes first.
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
CELL_MAX_W = 480    # a cell wider than this wraps onto another line within its band
WRAP_GAP = 28       # between wrapped lines (room for a note above the lower boxes)
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

    def line_width(ns):
        return sum(node_width(n) for n in ns) + NODE_GAP * max(0, len(ns) - 1)

    def cell_lines(row, col):
        """Split a cell into lines: forced by break_before, or when too wide."""
        lines = []
        for n in cells.get((row, col), []):
            if not lines or n.get("break_before") or line_width(lines[-1] + [n]) > CELL_MAX_W:
                lines.append([n])
            else:
                lines[-1].append(n)
        return lines

    def cell_width(row, col):
        return max((line_width(l) for l in cell_lines(row, col)), default=0)

    def cell_height(row, col):
        k = len(cell_lines(row, col))
        return k * NODE_H + max(0, k - 1) * WRAP_GAP

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
        used = [c for r, c in cells if r == code]
        h = max(cell_height(code, c) for c in used) + 2 * BAND_PAD if used else EMPTY_BAND
        out.bands.append({"code": code, "name": name, "y": y, "h": h})
        y += h
    out.height = y + MARGIN
    band_at = {b["code"]: b for b in out.bands}
    row_index = {code: i for i, (code, _) in enumerate(frame)}

    # Boxes: each line of a cell centred in its column; the lines centred in the band.
    for (row, col) in cells:
        c, b = col_at[col], band_at[row]
        by = b["y"] + (b["h"] - cell_height(row, col)) / 2
        for line in cell_lines(row, col):
            bx = c["x"] + (c["w"] - line_width(line)) / 2
            for n in line:
                w = node_width(n)
                out.boxes[n["id"]] = (bx, by, w, NODE_H)
                bx += w + NODE_GAP
            by += NODE_H + WRAP_GAP

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
#   view:    {id, title, kind: section}
#   floors:  [{id, title}]                          top to bottom
#   rooms:   [{id, label, floor}]                   left to right within each floor
#   devices: [{id, label, room, caption: [lines], status}]   in order within a room
#   links:   [{from, to, kind, tag}]                kind: wired | radio | tie | flow
#
# Each floor lays out its own rooms (floors don't share columns). Devices sit
# inside their room, side by side, wrapping when a row would exceed ROOM_MAX_W. Radio links
# are straight lines (radio goes through floors); every other link is routed
# with right angles, like cabling, turning at the edge of the target's floor.

SECTION_GUTTER = 120   # left margin for floor names
ROOM_GAP = 12
ROOM_MIN_W = 124
ROOM_PAD = 20          # inside a floor band, above and below the rooms
ROOM_HEAD = 30         # room label strip at the top of a room
ROOM_INNER = 10        # padding inside a room around its devices
DEVICE_H = 24
DEVICE_GAP = 12
ROOM_MAX_W = 560       # a room's devices wrap onto another row beyond this width
SMALL_CHAR_W = 6.2     # estimated width of one 11px character
CAPTION_LINE = 13


def _device_size(d):
    box_w = max(56, len(d.get("label", d["id"])) * SMALL_CHAR_W + 16)
    caption = d.get("caption") or []
    cell_w = max([box_w] + [len(c) * SMALL_CHAR_W for c in caption])
    cell_h = DEVICE_H + (4 + CAPTION_LINE * len(caption) if caption else 0)
    return box_w, cell_w, cell_h


def section_layout(view):
    meta = view["view"]
    if not meta.get("title", "").strip():
        raise ValueError(f"View {meta.get('id')!r} needs a title stating what it shows.")
    floor_ids = [f["id"] for f in view["floors"]]
    rooms_by_floor = {fid: [] for fid in floor_ids}
    room_floor = {}
    for r in view["rooms"]:
        if r["id"] in room_floor:
            raise ValueError(f"Duplicate room {r['id']!r}")
        if r["floor"] not in rooms_by_floor:
            raise ValueError(f"Room {r['id']!r}: unknown floor {r['floor']!r} (expected one of {floor_ids})")
        rooms_by_floor[r["floor"]].append(r)
        room_floor[r["id"]] = r["floor"]

    devices_by_room = {rid: [] for rid in room_floor}
    for d in view.get("devices", []):
        if d["room"] not in devices_by_room:
            raise ValueError(f"Device {d['id']!r}: unknown room {d['room']!r}")
        devices_by_room[d["room"]].append(d)

    # Size each room from its devices: rows that wrap by width.
    room_size, device_rows = {}, {}
    for rid, ds in devices_by_room.items():
        rows = []
        for d in ds:
            cell = _device_size(d)[1]
            if rows and sum(_device_size(x)[1] for x in rows[-1]) + DEVICE_GAP * len(rows[-1]) + cell \
                    + 2 * ROOM_INNER <= ROOM_MAX_W:
                rows[-1].append(d)
            else:
                rows.append([d])
        device_rows[rid] = rows
        label = next(r for rs in rooms_by_floor.values() for r in rs if r["id"] == rid)
        w = max(ROOM_MIN_W, len(label.get("label", rid)) * CHAR_W + LABEL_PAD)
        h = ROOM_HEAD + ROOM_INNER
        for row in rows:
            sizes = [_device_size(d) for d in row]
            w = max(w, sum(s[1] for s in sizes) + DEVICE_GAP * (len(row) - 1) + 2 * ROOM_INNER)
            h += max(s[2] for s in sizes) + DEVICE_GAP
        room_size[rid] = (w, max(h, 72))

    out = Layout(width=0, height=0)
    out.containers, out.captions, out.room_floor, out.row_bottom = {}, {}, room_floor, {}
    band_of = {}
    y, widest = MARGIN, 0
    for f in view["floors"]:
        rooms = rooms_by_floor[f["id"]]
        inner = max((room_size[r["id"]][1] for r in rooms), default=72)
        h = inner + 2 * ROOM_PAD
        band = {"code": f["title"], "name": "", "y": y, "h": h}
        out.bands.append(band)
        band_of[f["id"]] = band
        x = SECTION_GUTTER
        for r in rooms:
            w, rh = room_size[r["id"]]
            rx, ry = x, y + ROOM_PAD
            out.containers[r["id"]] = (rx, ry, w, inner)
            # Devices, row by row, left aligned inside the room.
            dy = ry + ROOM_HEAD
            for row in device_rows[r["id"]]:
                dx = rx + ROOM_INNER
                row_h = 0
                row_h = max(_device_size(d)[2] for d in row)
                for d in row:
                    box_w, cell_w, cell_h = _device_size(d)
                    out.row_bottom[d["id"]] = dy + row_h      # below this row's captions
                    bx = dx + (cell_w - box_w) / 2
                    out.boxes[d["id"]] = (bx, dy, box_w, DEVICE_H)
                    out.captions[d["id"]] = [(dx + cell_w / 2, dy + DEVICE_H + 4 + CAPTION_LINE * (k + 1) - 3, c)
                                             for k, c in enumerate(d.get("caption") or [])]
                    dx += cell_w + DEVICE_GAP
                    row_h = max(row_h, cell_h)
                dy += row_h + DEVICE_GAP
            x += w + ROOM_GAP
        widest = max(widest, x - ROOM_GAP)
        y += h
    out.width = widest + MARGIN
    out.height = y + MARGIN

    # Links.
    device_floor = {d["id"]: room_floor[d["room"]] for d in view.get("devices", [])}
    lanes = {}   # turning y -> how many routes already turn there
    for link in view.get("links", []):
        for end in ("from", "to"):
            if link[end] not in out.boxes:
                raise ValueError(f"Link {link['from']} - {link['to']}: no device {link[end]!r}")
        sx, sy, sw, sh = out.boxes[link["from"]]
        tx, ty, tw, th = out.boxes[link["to"]]
        sf, tf = device_floor[link["from"]], device_floor[link["to"]]
        if abs(sy - ty) < 0.5 and link.get("kind") == "radio":
            # Radio along a row: arc below the row, clear of the boxes between.
            p, q = (sx + sw / 2, sy + sh), (tx + tw / 2, ty + th)
            dip = 30                                  # depth of the arc below the boxes
            out.routes.append({"edge": link, "points": [p, q],
                               "control": ((p[0] + q[0]) / 2, p[1] + 2 * dip)})
            continue
        between = [b for i, b in out.boxes.items() if i not in (link["from"], link["to"])
                   and abs(b[1] - sy) < 0.5 and min(sx, tx) < b[0] < max(sx, tx)]
        if abs(sy - ty) < 0.5 and between:
            # Same row, but another device sits between: run over the row (above the
            # boxes, below the room name), from the edges that face each other.
            # Over rather than under, because captions sit under the boxes.
            ey = sy - 6
            if tx > sx:
                p, q = (sx + sw - 8, sy), (tx + 8, ty)
            else:
                p, q = (sx + 8, sy), (tx + tw - 8, ty)
            out.routes.append({"edge": link, "points": [p, (p[0], ey), (q[0], ey), q]})
            continue
        if abs(sy - ty) < 0.5:                       # same device row: side to side
            if tx > sx:
                pts = [(sx + sw, sy + sh / 2), (tx, ty + th / 2)]
            else:
                pts = [(sx, sy + sh / 2), (tx + tw, ty + th / 2)]
        else:
            down = ty > sy
            lo, hi = max(sx, tx), min(sx + sw, tx + tw)
            if link.get("kind") != "radio" and hi - lo > 8:
                # The boxes overlap side to side: drop straight between them, at the
                # point nearest the middle that doesn't pass through another device.
                y0, y1 = (sy + sh, ty) if down else (ty + th, sy)
                blockers = [b for i, b in out.boxes.items() if i not in (link["from"], link["to"])
                            and b[1] < y1 and b[1] + b[3] > y0]
                mid = (lo + hi) / 2
                candidates = sorted((lo + 6 + k * 2 for k in range(int((hi - lo - 12) / 2) + 1)),
                                    key=lambda x: abs(x - mid))
                mx = next((x for x in candidates
                           if not any(b[0] - 4 <= x <= b[0] + b[2] + 4 for b in blockers)), mid)
                pts = [(mx, sy + sh if down else sy), (mx, ty if down else ty + th)]
            else:
                p = (sx + sw / 2, sy + sh if down else sy)
                q = (tx + tw / 2, ty if down else ty + th)
                if link.get("kind") == "radio" or abs(p[0] - q[0]) < 0.5:
                    pts = [p, q]
                else:
                    if sf == tf:                      # same floor, different rows
                        ey = (p[1] + q[1]) / 2
                    else:                             # turn near the target floor's edge,
                        b = band_of[tf]               # each route in its own lane
                        edge = b["y"] if down else b["y"] + b["h"]
                        k = lanes.get(edge, 0)
                        lanes[edge] = k + 1
                        ey = edge - 6 * k if down else edge + 6 * k
                    pts = [p, (p[0], ey), (q[0], ey), q]
        out.routes.append({"edge": link, "points": pts})
    return out
