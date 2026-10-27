"""Views of the house, built from its public export (content/models/house.yaml).

The export is produced by the house repo's view policy; this adapter only
reshapes it into view data and never sees anything the policy held back.
"""
from pathlib import Path

import yaml

EXPORT = Path(__file__).resolve().parent.parent.parent / "content" / "models" / "house.yaml"

MEDIUM = {"ethernet": "Ethernet", "moca": "MoCA", "zigbee": "Zigbee", "wifi": "WiFi"}
DEFAULT_WIRED = "ethernet"   # untagged in the figure; the legend says so
RADIO = {"zigbee", "wifi"}
TYPE_LABEL = {"moca_adapter": "MoCA adapter", "switch": "Switch",
              "access_point": "Access point", "isp_connection": "Internet uplink"}
MEASURES_LABEL = [({"temperature", "humidity"}, "Climate"), ({"moisture"}, "Leak")]

INTERNET = "internet"   # a container in the Outside band for things beyond the house


def load():
    return yaml.safe_load(EXPORT.read_text(encoding="utf-8"))


def name(entry):
    """Public label if the policy set one, else the HA name, else the id."""
    return entry.get("label") or entry.get("name") or entry["id"].replace("_", " ").capitalize()


def floors_and_rooms(spaces):
    floors = sorted((s for s in spaces if s["type"] == "floor"), key=lambda s: -s.get("level", 0))
    outside = [s for s in spaces if s["type"] == "environment"]
    view_floors = [{"id": "outside", "title": "Outside"}] if outside else []
    view_floors += [{"id": f["id"], "title": name(f)} for f in floors]
    rooms = [{"id": s["id"], "label": name(s), "floor": "outside"} for s in outside]
    rooms.append({"id": INTERNET, "label": "Internet", "floor": "outside"})
    for f in floors:
        inside = sorted((s for s in spaces if s["type"] == "room" and s.get("part_of") == f["id"]),
                        key=lambda s: s.get("order", 99))
        rooms += [{"id": s["id"], "label": name(s), "floor": f["id"]} for s in inside]
    return view_floors, rooms


def section(data=None):
    """The house in section, with every placed device and how it connects."""
    data = data or load()
    floors, rooms = floors_and_rooms(data["spaces"])
    room_ids = {r["id"] for r in rooms}
    devices, links, skipped = [], [], []

    services = data.get("services", [])
    host_of = {s["id"]: s.get("hosted_on") for s in services}

    def add(entry, label, room, caption=()):
        if room not in room_ids:
            skipped.append(entry["id"])
            return
        devices.append({"id": entry["id"], "label": label, "room": room,
                        "caption": list(caption), "status": entry.get("status")})

    # Network gear first, then hosts, then sensors, then what the sensors watch.
    for n in data.get("nodes", []):
        if n.get("type") == "placeholder":
            continue                       # stands in for unrecorded data; nothing to draw
        room = INTERNET if n.get("type") == "isp_connection" else n.get("located_in")
        add(n, n.get("label") or TYPE_LABEL.get(n.get("type")) or name(n), room)
    for h in data.get("hosts", []):
        runs = [f"{name(s)} (planned)" if s.get("status") == "planned" else (s.get("product") or name(s))
                for s in services if s.get("hosted_on") == h["id"]]
        add(h, name(h), h.get("located_in"), runs)
    for i in data.get("instruments", []):
        measures = set(i.get("measures") or [])
        label = next((l for m, l in MEASURES_LABEL if m <= measures), name(i))
        medium = (i.get("link") or {}).get("medium")
        add(i, label, i.get("located_in"), [MEDIUM.get(medium, medium)] if medium else [])
    observed = {i.get("observes") for i in data.get("instruments", [])}
    for e in data.get("equipment", []):
        if e["id"] in observed:
            add(e, name(e), e.get("located_in"))
    for x in data.get("external_sources", []):
        if x.get("status", "active") == "active":
            add(x, "Weather feed" if x.get("type") == "weather_service" else name(x), INTERNET,
                [x["id"].replace("_", " ").title()])

    placed = {d["id"] for d in devices}

    def link(a, b, kind, tag=None):
        if a in placed and b in placed and a != b:
            links.append({"from": a, "to": b, "kind": kind, **({"tag": tag} if tag else {})})

    # Cables and radio, from the network, hosts and sensors.
    def tag(medium):
        return None if medium in RADIO or medium == DEFAULT_WIRED else MEDIUM.get(medium, medium)

    for l in data.get("links", []):
        link(l["from"], l["to"], "radio" if l.get("medium") in RADIO else "wired", tag(l.get("medium")))
    for d in data.get("hosts", []) + data.get("instruments", []):
        ln = d.get("link") or {}
        target = host_of.get(ln.get("to"), ln.get("to"))   # a service resolves to its host
        medium = ln.get("medium")
        link(d["id"], target, "radio" if medium in RADIO else "wired", tag(medium))
    # A sensor and the thing it watches.
    for i in data.get("instruments", []):
        if i.get("observes"):
            link(i["id"], i["observes"], "tie")
    # Data flows are logical, not physical, so they belong to the ISA-95 view.
    # Here, external data (the weather feed) sits beside the internet uplink:
    # physically it arrives the way all internet traffic does.

    if skipped:
        print(f"  house-physical: not placed (no room in the export): {', '.join(sorted(skipped))}")

    return {
        "view": {
            "id": "house-physical",
            "kind": "section",
            "title": (
                "The house in section, showing where each device sits and how it connects. "
                "Zigbee sensors on every floor reach the dongle on the Raspberry Pi in the basement "
                "theatre by radio; cables run from the router in the gym over MoCA to the theatre "
                "switch and the living room access point; the weather feed arrives over the internet uplink."
            ),
        },
        "floors": floors,
        "rooms": rooms,
        "devices": devices,
        "links": links,
    }




# ---- Logical view: the same devices by ISA-95 level ---------------------------

def logical(data=None):
    """The house's data path on ISA-95 levels, in columns by where each piece runs."""
    data = data or load()
    hosts = {h["id"]: h for h in data.get("hosts", [])}
    services = {s["id"]: s for s in data.get("services", [])}
    instruments = data.get("instruments", [])
    externals = data.get("external_sources", [])

    # Columns: the field, each host that runs part of the data path, then outside.
    on_path = [s for s in services.values() if s.get("isa95")]
    host_order = []
    for s in on_path:
        if s.get("hosted_on") in hosts and s["hosted_on"] not in host_order:
            host_order.append(s["hosted_on"])
    columns = ([{"id": "field", "title": "In the rooms"}]
               + [{"id": h, "title": name(hosts[h])} for h in host_order]
               + [{"id": "outside", "title": "Outside"}])

    nodes, edges = [], []

    # L0: equipment on the operations path. Observed things tie to their sensor
    # group; unobserved things get a path that stops.
    observed = {i.get("observes"): i for i in instruments if i.get("observes")}
    # Observed things last, so they sit under their sensors and the tie stays short.
    equipment = sorted((e for e in data.get("equipment", []) if e.get("isa95") == "L0"),
                       key=lambda e: e["id"] in observed)
    # L1: sensors grouped by how they reach the system.
    by_medium = {}
    for i in instruments:
        by_medium.setdefault((i.get("link") or {}).get("medium"), []).append(i)
    # Groups that go through a gateway in the same row (Zigbee via the coordinator)
    # sit last, next to the gateway's column, so their line runs clear of the others.
    services_row = {s["id"]: s.get("isa95") for s in services.values()}
    by_medium = dict(sorted(by_medium.items(),
                            key=lambda kv: services_row.get((kv[1][0].get("link") or {}).get("to")) == "L1"))
    group_of = {}
    for medium, group in by_medium.items():
        if len(group) == 1:
            gid, label, kind = group[0]["id"], f"{MEDIUM.get(medium, medium)} sensor", "asset"
        else:
            gid, label, kind = f"{medium}_sensors", f"{MEDIUM.get(medium, medium)} sensors ×{len(group)}", "group"
        nodes.append({"id": gid, "label": label, "kind": kind, "row": "L1", "col": "field"})
        for i in group:
            group_of[i["id"]] = gid
    # Three kinds of L0 equipment:
    #   not observed yet  a gap (connection planned or undecided): path that stops
    #   observed          watched by a sensor: tied to its sensor group
    #   estimated         never to be connected, by choice: marked "estimated", no stub
    # Anything with a line going up sits on the top line of the cell; the
    # estimated appliances start a second line below it.
    gap = [e for e in equipment if e["id"] not in observed and e.get("connected") != "never"]
    watched = [e for e in equipment if e["id"] in observed]
    chosen = [e for e in equipment if e["id"] not in observed and e.get("connected") == "never"]
    for e in gap:
        nodes.append({"id": e["id"], "label": name(e), "kind": "asset", "row": "L0", "col": "field",
                      "no_path": "up", "no_path_note": "not observed yet"})
    for e in watched:
        nodes.append({"id": e["id"], "label": name(e), "kind": "asset", "row": "L0", "col": "field"})
        edges.append({"from": e["id"], "to": group_of[observed[e["id"]]["id"]], "kind": "tie",
                      "label": "leak sensor" if "moisture" in (observed[e["id"]].get("measures") or [])
                      else "sensor"})
    for k, e in enumerate(chosen):
        nodes.append({"id": e["id"], "label": name(e), "kind": "asset", "row": "L0", "col": "field",
                      "note": "estimated", "break_before": k == 0})

    # Services on the data path, in the column of their host.
    for s in on_path:
        nodes.append({"id": s["id"], "label": name(s), "kind": "system", "row": s["isa95"],
                      "col": s.get("hosted_on") if s.get("hosted_on") in hosts else "outside",
                      "status": s.get("status")})
    # External sources, outside. Bills are documents, so they are artifacts.
    for x in externals:
        nodes.append({"id": x["id"], "label": name(x), "row": x["isa95"], "col": "outside",
                      "kind": "artifact" if x.get("type") == "utility_billing" else "system",
                      "status": x.get("status")})

    ids = {n["id"] for n in nodes}
    # Sensors reach their system: Zigbee via the coordinator, WiFi direct (from the flows).
    for medium, group in by_medium.items():
        target = (group[0].get("link") or {}).get("to")
        gid = group_of[group[0]["id"]]
        if target in ids:
            edges.append({"from": gid, "to": target, "kind": "flow", "label": MEDIUM.get(medium)})
    for f in data.get("flows", []):
        a, b = group_of.get(f["from"], f["from"]), f["to"]
        if a in ids and b in ids and not any(e["from"] == a and e["to"] == b for e in edges):
            edge = {"from": a, "to": b, "kind": "flow", "status": f.get("status")}
            if a in group_of.values():
                edge["label"] = MEDIUM.get((next(i for i in instruments if group_of[i["id"]] == a)
                                            .get("link") or {}).get("medium"))
            edges.append(edge)

    return {
        "view": {
            "id": "house-logical",
            "rows": "isa95",
            "columns": columns,
            "title": (
                "The same house by ISA-95 level, in columns by where each piece runs. Zigbee sensors "
                "reach Home Assistant through the coordinator on the Raspberry Pi 5, and a WiFi sensor "
                "reaches it directly; readings climb to InfluxDB and Grafana on the NAS, with an ESC "
                "page planned on top. At the physical level, the furnace and the garage heater are not "
                "observed yet; the fridge is watched by a leak sensor; the water heater, stove, washer and "
                "dryer are deliberately left unconnected, their loads estimated. Utility bills are planned "
                "at the business level."
            ),
        },
        "nodes": nodes,
        "edges": edges,
    }


VIEWS = [section, logical]
