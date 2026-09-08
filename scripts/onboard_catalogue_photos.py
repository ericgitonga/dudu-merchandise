"""Resize source photos into static/images/catalogue/{thumbs,full}/ and add their manifest
entries, following the established convention: `full` capped at 1400px on the long side (left
alone if already smaller — never upscaled), `thumb` capped at 420px on the long side (exactly
30% of `full`'s target). Both dimensions come from Pillow at save time, so there's no separate
add_catalogue_dimensions.py pass needed afterward for these entries.

Edit ONBOARD below for each batch, then run:

    conda run -n ds python scripts/onboard_catalogue_photos.py
"""

import json
from pathlib import Path

from PIL import Image

BASE_DIR = Path(__file__).parent.parent
CATALOGUE_DIR = BASE_DIR / "static" / "images" / "catalogue"
MANIFEST = CATALOGUE_DIR / "manifest.json"

FULL_LONG_SIDE = 1400
THUMB_LONG_SIDE = 420

# (source path, new id, category)
ONBOARD = [
    (
        "/home/gitonga/Develop/projects/extras/projects/dudu-merchandise/assets/catalogue/Scorpions/sc-002.jpg",
        "sc-002", "Scorpions",
    ),
    (
        "/home/gitonga/Develop/projects/extras/projects/dudu-merchandise/assets/catalogue/Scorpions/sc-003.jpg",
        "sc-003", "Scorpions",
    ),
    (
        "/home/gitonga/Develop/projects/extras/projects/dudu-merchandise/assets/catalogue/Scorpions/sc-004.jpg",
        "sc-004", "Scorpions",
    ),
    (
        "/home/gitonga/Develop/projects/extras/projects/dudu-merchandise/assets/catalogue/Other/ot-001.jpg",
        "ot-001", "Other",
    ),
    (
        "/home/gitonga/Develop/projects/extras/projects/dudu-merchandise/assets/catalogue/Other/ot-011.jpg",
        "ot-011", "Other",
    ),
    (
        "/home/gitonga/Develop/projects/extras/projects/dudu-merchandise/assets/catalogue/Other/ot-012.jpg",
        "ot-012", "Other",
    ),
]


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

    for source, new_id, category in ONBOARD:
        if new_id in existing_ids:
            raise ValueError(f"id {new_id} already exists in manifest — refusing to overwrite")

        src_im = Image.open(source).convert("RGB")

        full_im = _resized(src_im, FULL_LONG_SIDE)
        full_path = CATALOGUE_DIR / "full" / f"{new_id}.jpg"
        full_im.save(full_path, "JPEG", quality=85, optimize=True)

        thumb_im = _resized(full_im, THUMB_LONG_SIDE)
        thumb_path = CATALOGUE_DIR / "thumbs" / f"{new_id}.jpg"
        thumb_im.save(thumb_path, "JPEG", quality=85, optimize=True)

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
    print(f"Manifest updated, {len(ONBOARD)} new entries.")


if __name__ == "__main__":
    main()
