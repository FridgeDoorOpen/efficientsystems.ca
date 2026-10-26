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
        room = INTERNET if n.get("type") == "isp_connection" else n.get("located_in")
        add(n, n.get("label") or TYPE_LABEL.get(n.get("type")) or name(n), room)
    for h in data.get("hosts", []):
        runs = [s.get("product") or name(s) for s in services if s.get("hosted_on") == h["id"]]
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


VIEWS = [section]
