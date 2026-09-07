"""Fills in width/height for every catalogue entry in manifest.json that's missing them, read
from the full-resolution image (thumb and full share the same aspect ratio — thumbs are
proportional resizes). Idempotent: entries that already have both fields are left alone, so it's
safe to re-run after adding new photos.

See issue #38: baking dimensions into the manifest means the Prints/Apparel mockup scripts never
need to load an image at runtime just to compute aspect ratio — the add-to-cart button can enable
the instant a photo is selected, with no network dependency at all.

Run after adding new photos to static/images/catalogue/ (see README's "Catalogue images"
section):

    conda run -n ds python scripts/add_catalogue_dimensions.py
"""

import json
from pathlib import Path

from PIL import Image

BASE_DIR = Path(__file__).parent.parent
MANIFEST = BASE_DIR / "static" / "images" / "catalogue" / "manifest.json"


def main():
    data = json.loads(MANIFEST.read_text())
    updated = 0
    for img in data["images"]:
        if "width" in img and "height" in img:
            continue
        full_path = BASE_DIR / img["full"].lstrip("/")
        with Image.open(full_path) as im:
            img["width"], img["height"] = im.size
        updated += 1

    if updated:
        MANIFEST.write_text(json.dumps(data, indent=2))
        print(f"Updated {updated} catalogue entr{'y' if updated == 1 else 'ies'} with width/height.")
    else:
        print("Every catalogue entry already has width/height — nothing to do.")


if __name__ == "__main__":
    main()
