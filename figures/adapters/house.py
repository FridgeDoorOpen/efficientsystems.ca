"""Views of the house, built from its public export (content/models/house.yaml).

The export is produced by the house repo's view policy; this adapter only
reshapes it into view data and never sees anything the policy held back.
"""
from pathlib import Path

import yaml

EXPORT = Path(__file__).resolve().parent.parent.parent / "content" / "models" / "house.yaml"


def load():
    return yaml.safe_load(EXPORT.read_text(encoding="utf-8"))


def name(entry):
    """Public label if the policy set one, else the HA name, else the id."""
    return entry.get("label") or entry.get("name") or entry["id"].replace("_", " ").capitalize()


def section(data=None):
    """The house in section: outside on top, then floors from highest level down."""
    data = data or load()
    spaces = data["spaces"]
    floors = sorted((s for s in spaces if s["type"] == "floor"), key=lambda s: -s.get("level", 0))
    outside = [s for s in spaces if s["type"] == "environment"]

    view_floors = [{"id": "outside", "title": "Outside"}] if outside else []
    view_floors += [{"id": f["id"], "title": name(f)} for f in floors]

    rooms = [{"id": s["id"], "label": name(s), "floor": "outside"} for s in outside]
    for f in floors:
        inside = sorted((s for s in spaces if s["type"] == "room" and s.get("part_of") == f["id"]),
                        key=lambda s: s.get("order", 99))
        rooms += [{"id": s["id"], "label": name(s), "floor": f["id"]} for s in inside]

    return {
        "view": {
            "id": "house-section",
            "kind": "section",
            "title": (
                "The house in section: the yard above, then the upstairs, main floor and "
                "basement, each with its rooms left to right in rough floor-plan order."
            ),
        },
        "floors": view_floors,
        "rooms": rooms,
    }


VIEWS = [section]
