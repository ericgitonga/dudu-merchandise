"""One-time migration: renumber every catalogue photo from a global numeric id (e.g. `169.jpg`)
to a per-category, letter-prefixed id (e.g. `t-001.jpg` for True Bugs) — see issue #82.

Within each category, entries are renumbered in ascending order of their current numeric id, so
the lowest surviving id in a category becomes `<prefix>-001`. Renames both `thumbs/` and `full/`
files and rewrites `manifest.json` in place. Idempotent-ish: an entry whose id already matches
the new `<prefix>-NNN` pattern is left alone, so it's safe to re-run after adding new photos with
the next unused number for their category (see README's "Catalogue images" section).

Run:

    conda run -n ds python scripts/renumber_catalogue.py
"""

import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
CATALOGUE_DIR = BASE_DIR / "static" / "images" / "catalogue"
MANIFEST = CATALOGUE_DIR / "manifest.json"

PREFIXES = {
    "Ants": "a",
    "Bees": "be",
    "Beetles": "bt",
    "Butterflies": "bu",
    "Caterpillars": "c",
    "Damselflies": "da",
    "Dragonflies": "dr",
    "Flies": "f",
    "Mantises": "ma",
    "Moths": "mo",
    "Neuroptera": "n",
    "Orthoptera": "or",
    "Other": "ot",
    "Spiders": "s",
    "True Bugs": "t",
    "Wasps": "w",
}

NEW_ID_RE = re.compile(r"^[a-z]{1,2}-\d{3}$")


def main():
    data = json.loads(MANIFEST.read_text())
    images = data["images"]

    by_category = {}
    for img in images:
        by_category.setdefault(img["category"], []).append(img)

    renamed = 0
    for category, entries in by_category.items():
        prefix = PREFIXES[category]
        pending = [img for img in entries if not NEW_ID_RE.match(img["id"])]
        pending.sort(key=lambda img: int(img["id"]))

        existing_numbers = {
            int(img["id"].split("-", 1)[1])
            for img in entries
            if NEW_ID_RE.match(img["id"]) and img["id"].startswith(f"{prefix}-")
        }
        next_n = max(existing_numbers, default=0) + 1

        for img in pending:
            new_id = f"{prefix}-{next_n:03d}"
            next_n += 1

            for subdir in ("thumbs", "full"):
                old_path = CATALOGUE_DIR / subdir / f"{img['id']}.jpg"
                new_path = CATALOGUE_DIR / subdir / f"{new_id}.jpg"
                old_path.rename(new_path)

            img["id"] = new_id
            img["thumb"] = f"/static/images/catalogue/thumbs/{new_id}.jpg"
            img["full"] = f"/static/images/catalogue/full/{new_id}.jpg"
            renamed += 1

    if renamed:
        MANIFEST.write_text(json.dumps(data, indent=2) + "\n")
        print(f"Renumbered {renamed} catalogue entr{'y' if renamed == 1 else 'ies'}.")
    else:
        print("Every catalogue entry already uses the <prefix>-NNN scheme — nothing to do.")


if __name__ == "__main__":
    main()
