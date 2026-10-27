"""The home page figure: context passed in documents, versus one shared model.

An argument figure, drawn after JPL's document-based to model-based systems
engineering figure (in the NASA MBSE paper on the Lineage page), recast for
an energy operator. Coordinates are computed here rather than laid out from
data, because the arrangement is the argument.

Run:  python -m figures.home
"""
import math
from pathlib import Path

from figures.grammar import Figure

OUT = Path(__file__).parent.parent / "content" / "home-shared-context.svg"

TITLE = (
    "Two ways to run the same company. Left, today: operations, scheduling, measurement, "
    "maintenance, commercial and AI agents pass context to each other in documents, carried by "
    "people, in a tangle that grows with every new participant. Right: the same six roles each "
    "connect to one shared model of context, and each reads its own view of it."
)

ROLES = ["Operations", "Scheduling", "Commercial", "AI agents", "Maintenance", "Measurement"]
# Who hands documents to whom today (indices into ROLES).
HANDOFFS = [(0, 1), (0, 5), (0, 4), (1, 2), (1, 5), (2, 3), (2, 4), (3, 5), (4, 5), (3, 1)]

W, H = 786, 330
RX, RY = 92, 92           # the ring of roles
CY = 182
LEFT_CX, RIGHT_CX = 178, 604
ARROW = (362, 420)        # the transition arrow between the panels
CHAR_W = 6.2              # 11px label character estimate


def ring(cx):
    """Role positions around a centre, starting at the top and going clockwise."""
    pts = []
    for k in range(len(ROLES)):
        a = math.radians(-90 + k * 360 / len(ROLES))
        pts.append((cx + RX * math.cos(a), CY + RY * math.sin(a)))
    return pts


def role(fig, x, y, name, cx):
    """A role and its name, placed outside the ring so lines never cross it:
    above or below for the top and bottom roles, beside for the others."""
    fig.role(x - 8, y - 8, 16, 16)
    if abs(x - cx) < 1:
        fig.note(x, y - 14 if y < CY else y + 24, name, anchor="middle")
    elif x < cx:
        fig.note(x - 14, y + 4, name, anchor="end")
    else:
        fig.note(x + 14, y + 4, name)


def build():
    fig = Figure("home", W, H, title=TITLE)

    # Left: today, context travels in documents.
    fig.heading(LEFT_CX, 28, "Today · context in documents", anchor="middle")
    left = ring(LEFT_CX)
    for a, b in HANDOFFS:
        (ax, ay), (bx, by) = left[a], left[b]
        fig.line(ax, ay, bx, by, kind="human")
    for a, b in HANDOFFS:                    # a document on every handoff, drawn on top
        (ax, ay), (bx, by) = left[a], left[b]
        mx, my = ax + (bx - ax) * 0.42, ay + (by - ay) * 0.42
        fig.artifact(mx - 6, my - 8, 12, 16)
    for (x, y), name in zip(left, ROLES):
        role(fig, x, y, name, LEFT_CX)

    # Between: the transition.
    fig.line(ARROW[0], CY, ARROW[1], CY, kind="accent")

    # Right: one shared model, many views.
    fig.heading(RIGHT_CX, 28, "Shared context · one model, many views", anchor="middle")
    erx, ery = 58, 34
    for x, y in ring(RIGHT_CX):
        dx, dy = RIGHT_CX - x, CY - y
        d = math.hypot(dx, dy)
        ux, uy = dx / d, dy / d
        # Stop at the ellipse edge: solve (t·ux/erx)² + (t·uy/ery)² = 1 from the centre.
        t = 1 / math.sqrt((ux / erx) ** 2 + (uy / ery) ** 2)
        fig.line(x + ux * 12, y + uy * 12, RIGHT_CX - ux * (t + 3), CY - uy * (t + 3), kind="flow")
    fig.ellipse(RIGHT_CX, CY, erx, ery, "f-ring-core")
    fig.accent_text(RIGHT_CX, CY - 3, "Shared", anchor="middle")
    fig.accent_text(RIGHT_CX, CY + 13, "context", anchor="middle")
    for (x, y), name in zip(ring(RIGHT_CX), ROLES):
        role(fig, x, y, name, RIGHT_CX)
    return fig


def main():
    build().save(OUT, source="figures/home.py")
    print(f"Wrote content/{OUT.name}")


if __name__ == "__main__":
    main()
