"""Scans extras/projects/dudu-merchandise/assets/catalogue/ (outside this repo — the source-of-
truth original photos, organised into one subfolder per CATALOGUE_CATEGORIES value) for any
photo already named `<prefix>-NNN` that isn't in manifest.json yet, and onboards all of them:
resizes into static/images/catalogue/{thumbs,full}/ following the established convention (`full`
capped at 1400px on the long side, left alone if already smaller — never upscaled; `thumb`
capped at 420px, exactly 30% of `full`'s target) and appends the manifest entry directly, width/
height included, so no separate add_catalogue_dimensions.py pass is needed for these entries.

Only picks up photos already renamed to the `<prefix>-NNN` scheme — a category folder's other,
not-yet-curated pool photos (arbitrary filenames, or ids already covering a gap) are left alone.
Add a new prefix to PREFIX_TO_CATEGORY here first if the batch introduces a new category (and
add that category to CATALOGUE_CATEGORIES in app.py, and the prefix table in README.md).

Run:

    conda run -n ds python scripts/onboard_catalogue_photos.py
"""

import json
import re
from pathlib import Path

from PIL import Image

BASE_DIR = Path(__file__).parent.parent
CATALOGUE_DIR = BASE_DIR / "static" / "images" / "catalogue"
MANIFEST = CATALOGUE_DIR / "manifest.json"
EXTRAS_DIR = Path("/home/gitonga/Develop/projects/extras/projects/dudu-merchandise/assets/catalogue")

FULL_LONG_SIDE = 1400
THUMB_LONG_SIDE = 420

PREFIX_TO_CATEGORY = {
    "a": "Ants", "be": "Bees", "bt": "Beetles", "bu": "Butterflies", "c": "Caterpillars",
    "da": "Damselflies", "dr": "Dragonflies", "f": "Flies", "ma": "Mantises", "mo": "Moths",
    "n": "Neuroptera", "or": "Orthoptera", "ot": "Other", "s": "Spiders", "sc": "Scorpions",
    "st": "Stick Insects", "t": "True Bugs", "w": "Wasps",
}

ID_PATTERN = re.compile(r"^([a-z]{1,2})-(\d{3})$")


def _resized(im, long_side):
    w, h = im.size
    if max(w, h) <= long_side:
        return im
    scale = long_side / max(w, h)
    return im.resize((round(w * scale), round(h * scale)), Image.LANCZOS)


def main():
    data = json.loads(MANIFEST.read_text())
    images = data["images"]
    existing_ids = {img["id"] for img in images}

    to_onboard = []
    for cat_dir in sorted(EXTRAS_DIR.iterdir()):
        if not cat_dir.is_dir():
            continue
        for source in sorted(cat_dir.iterdir()):
            if not source.is_file():
                continue
            match = ID_PATTERN.match(source.stem)
            if not match or source.stem in existing_ids:
                continue
            prefix = match.group(1)
            category = PREFIX_TO_CATEGORY.get(prefix)
            if category is None:
                raise ValueError(
                    f"unknown prefix {prefix!r} for {source} — add it to PREFIX_TO_CATEGORY"
                )
            to_onboard.append((source, source.stem, category))

    if not to_onboard:
        print("Every <prefix>-NNN photo in extras is already in the manifest — nothing to do.")
        return

    for source, new_id, category in to_onboard:
        src_im = Image.open(source).convert("RGB")

        full_im = _resized(src_im, FULL_LONG_SIDE)
        (CATALOGUE_DIR / "full" / f"{new_id}.jpg").parent.mkdir(parents=True, exist_ok=True)
        full_im.save(CATALOGUE_DIR / "full" / f"{new_id}.jpg", "JPEG", quality=85, optimize=True)

        thumb_im = _resized(full_im, THUMB_LONG_SIDE)
        thumb_im.save(CATALOGUE_DIR / "thumbs" / f"{new_id}.jpg", "JPEG", quality=85, optimize=True)

        images.append({
            "id": new_id,
            "thumb": f"/static/images/catalogue/thumbs/{new_id}.jpg",
            "full": f"/static/images/catalogue/full/{new_id}.jpg",
            "width": full_im.width,
            "height": full_im.height,
            "category": category,
        })
        print(f"onboarded {source} -> {new_id} ({category}), {full_im.size}")

    MANIFEST.write_text(json.dumps(data, indent=2) + "\n")
    print(f"Manifest updated, {len(to_onboard)} new entries, {len(images)} total.")


if __name__ == "__main__":
    main()
