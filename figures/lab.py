"""Draw every example view into content/lab/, for the unlisted /lab/ page.

Run:  python -m figures.lab
"""
from pathlib import Path

from figures.adapters import house
from figures.views import draw, load

HERE = Path(__file__).parent
OUT = HERE.parent / "content" / "lab"


def main():
    OUT.mkdir(exist_ok=True)
    for src in sorted((HERE / "examples").glob("*.yaml")):
        view = load(src)
        out = OUT / f"{view['view']['id']}.svg"
        draw(view).save(out, source=f"figures/views.py from figures/examples/{src.name}")
        print(f"Wrote content/lab/{out.name}")

    # Views built from model exports.
    for make in house.VIEWS:
        view = make()
        out = OUT / f"{view['view']['id']}.svg"
        draw(view).save(out, source=f"figures/adapters/house.py ({make.__name__}) from content/models/house.yaml")
        print(f"Wrote content/lab/{out.name}")


if __name__ == "__main__":
    main()
