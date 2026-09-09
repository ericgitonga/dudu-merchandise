"""One-off (rerunnable) backfill: generates the `thumb_sm` variant (168px long side — 2x the
mobile picker's 84px CSS box, issue #102) for every manifest entry that doesn't have one yet,
resizing from the existing `full/` image (never re-touches the original source), and adds the
`thumb_sm` field to its manifest entry. Entries that already have `thumb_sm` are left alone, so
it's safe to run any time — same convention as `add_catalogue_dimensions.py`.

Run against both catalogues:

    conda run -n ds python scripts/generate_thumb_sm.py static/images/catalogue
    conda run -n ds python scripts/generate_thumb_sm.py static/images/catalogue-e2e
"""

import json
import sys
from pathlib import Path

from PIL import Image

BASE_DIR = Path(__file__).parent.parent
THUMB_SM_LONG_SIDE = 168


def _resized(im, long_side):
    w, h = im.size
    if max(w, h) <= long_side:
        return im
    scale = long_side / max(w, h)
    return im.resize((round(w * scale), round(h * scale)), Image.LANCZOS)


def main():
    if len(sys.argv) != 2:
        raise SystemExit(f"usage: {sys.argv[0]} <catalogue-dir>")
    catalogue_dir = Path(sys.argv[1])
    manifest_path = catalogue_dir / "manifest.json"
    data = json.loads(manifest_path.read_text())
    images = data["images"]

    todo = [img for img in images if not img.get("thumb_sm")]
    if not todo:
        print(f"{manifest_path}: every entry already has thumb_sm — nothing to do.")
        return

    thumb_sm_dir = catalogue_dir / "thumbs-sm"
    thumb_sm_dir.mkdir(parents=True, exist_ok=True)

    for img in todo:
        full_path = BASE_DIR / img["full"].lstrip("/")
        src_im = Image.open(full_path).convert("RGB")
        thumb_sm_im = _resized(src_im, THUMB_SM_LONG_SIDE)
        out_path = thumb_sm_dir / f"{img['id']}.jpg"
        thumb_sm_im.save(out_path, "JPEG", quality=85, optimize=True)
        img["thumb_sm"] = f"/{catalogue_dir.as_posix()}/thumbs-sm/{img['id']}.jpg"
        print(f"{img['id']}: generated {out_path} ({thumb_sm_im.size})")

    manifest_path.write_text(json.dumps(data, indent=2) + "\n")
    print(f"{manifest_path}: backfilled thumb_sm for {len(todo)} entries.")


if __name__ == "__main__":
    main()
