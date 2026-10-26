"""Draw the site legend (content/legend.svg) from the grammar.

The legend is the grammar, so it is generated from the same code as every
other figure: if a shape changes in grammar.py, the legend changes with it.

Run:  python -m figures.legend
"""
from pathlib import Path

from figures.grammar import Figure

OUT = Path(__file__).parent.parent / "content" / "legend.svg"

TITLE = (
    "Legend: shapes for asset, system, role, process, decision, artifact and group; "
    "a dashed outline marks anything planned; "
    "lines for data flow, inferred flow, context carried by people, association and no path; "
    "physical links drawn as a heavy line for cables and a dash-dot line for radio; "
    "the accent colour marks the point; horizontal bands are ISA-95 levels; "
    "a grid of RAMI 4.0 layers by hierarchy level is the second frame."
)

ROW = 52          # vertical spacing between legend entries
SWATCH_W = 72     # width of each sample shape or line
SWATCH_H = 34

# Physical links, under column 1. (kind, label, note)
LINKS = [
    ("wired", "Wired link", "A cable. Untagged is Ethernet; others are tagged, e.g. MOCA."),
    ("radio", "Radio link", "Zigbee, WiFi. Straight, because radio goes through floors."),
]

# Column 1: things. (method, label, note)
THINGS = [
    ("asset", "Asset", "Physical equipment. Square corners, filled."),
    ("system", "System", "Software or platform. Rounded, open."),
    ("role", "Role", "A person or team, by role."),
    ("process", "Process", "How work moves."),
    ("decision", "Decision", "A judgment someone actually makes."),
    ("artifact", "Artifact", "A form, template, rating or document."),
    ("group", "Group", "Things read together as one."),
    ("planned", "Planned", "Decided on, not built yet. Shapes dashed; lines dashed, muted."),
]

# Column 2: lines. (kind, label, note)
LINES = [
    ("flow", "Data flow", "Documented."),
    ("inferred", "Inferred flow", "Believed, not documented."),
    ("human", "Carried by people", "Meetings, email, spreadsheets."),
    ("tie", "Association", "Belongs to, describes."),
    ("no_path", "No path", "Where a flow should continue, and doesn't."),
]


def swatch_box(kind, x, y):
    """The box a sample shape is drawn in. Roles and decisions are drawn
    smaller than the full swatch so they read at their natural size."""
    cx, cy = x + SWATCH_W / 2, y + SWATCH_H / 2
    if kind == "role":
        return cx - 12, cy - 12, 24, 24
    if kind == "decision":
        return cx - 20, cy - 19, 40, 38
    return x, y, SWATCH_W, SWATCH_H


def entry(fig, x, y, label, note, label_cls="label"):
    """The label and note beside a swatch whose top edge is at y."""
    getattr(fig, label_cls)(x, y + 14, label)
    fig.note(x, y + 30, note)


def build():
    fig = Figure("lg", 720, 600, title=TITLE)

    # Column 1: things
    x, text_x = 20, 110
    fig.heading(x, 28, "Things")
    for i, (kind, label, note) in enumerate(THINGS):
        y = 48 + i * ROW
        if kind == "planned":
            fig.system(*swatch_box(kind, x, y), planned=True)
        else:
            getattr(fig, kind)(*swatch_box(kind, x, y))
        entry(fig, text_x, y, label, note)

    # Physical links, below the things
    fig.heading(x, 488, "Physical links")
    for i, (kind, label, note) in enumerate(LINKS):
        y = 508 + i * ROW
        mid = y + SWATCH_H / 2
        fig.line(x, mid, x + SWATCH_W, mid, kind=kind)
        entry(fig, text_x, y, label, note)

    # Column 2: lines
    x, text_x = 390, 480
    fig.heading(x, 28, "Lines")
    for i, (kind, label, note) in enumerate(LINES):
        y = 48 + i * ROW
        mid = y + SWATCH_H / 2
        if kind == "no_path":
            fig.no_path(x, mid, x + 28, mid)
        else:
            fig.line(x, mid, x + SWATCH_W, mid, kind=kind)
        entry(fig, text_x, y, label, note)

    # Emphasis and frame
    fig.heading(x, 324, "Emphasis and frame")
    fig.line(x, 345, x + SWATCH_W, 345, kind="accent")
    entry(fig, text_x, 328, "The point", "The one thing the diagram argues.", "accent_text")

    fig.band(x, 372, SWATCH_W, 22)
    fig.band(x, 394, SWATCH_W, 22, alt=True)
    entry(fig, text_x, 376, "ISA-95 levels", "L0–1 at the bottom, L4 at the top.")

    fig.grid(x, 430, SWATCH_W, 34, rows=3, cols=4)
    entry(fig, text_x, 430, "RAMI 4.0 grid", "Layers as rows, hierarchy levels as columns.")

    return fig


def main():
    build().save(OUT, source="figures/legend.py")
    print(f"Wrote {OUT.relative_to(OUT.parent.parent)}")


if __name__ == "__main__":
    main()
