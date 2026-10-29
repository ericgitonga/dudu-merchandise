"""Generates 3D perspective-warped bookmark mockup strips (`static/images/catalogue/bookmarks/<id>.jpg`)
for the Classic Books bookmark scene (`static/images/mockup/bookmark.jpg`), and optionally saves
the flat horizontal 4:1 bookmark strip (`1499 x 375`) to `extras/projects/dudu-merchandise/assets/bookmarks/`.

Each photo's subject is detected and placed in the lower two-thirds of the vertical bookmark
(clear of the U-clip cutout in the upper third), and the background bokeh is smoothly extended
across the U-clip and rounded top cap using multi-scale 2D diffusion.

Can be imported by `scripts/onboard_catalogue_photos.py` or run standalone to backfill missing
`bookmarks/<id>.jpg` entries in `manifest.json`:

    conda run -n ds python scripts/generate_bookmarks.py
"""

import json
from pathlib import Path

import cv2
import numpy as np

TW, TH = 1499, 375
SLOT_W, SLOT_H = 251, 941

BASE_DIR = Path(__file__).parent.parent
CATALOGUE_DIR = BASE_DIR / "static" / "images" / "catalogue"
MANIFEST = CATALOGUE_DIR / "manifest.json"
EXTRAS_BOOKMARKS_DIR = Path("/home/gitonga/Develop/projects/extras/projects/dudu-merchandise/assets/bookmarks")


def heal_corner_watermarks(img: np.ndarray) -> np.ndarray:
    """Inpaint corner watermarks (signature in bottom-right or bottom-left) before bokeh extension."""
    h, w = img.shape[:2]
    out = img.copy()
    gray = cv2.cvtColor(out, cv2.COLOR_BGR2GRAY).astype(np.float32)
    local_med = cv2.medianBlur(gray.astype(np.uint8), 31).astype(np.float32)
    diff = np.abs(gray - local_med)

    mask = np.zeros((h, w), dtype=np.uint8)
    ry0 = int(h * 0.84)
    rx_right = int(w * 0.70)
    rx_left = int(w * 0.30)

    roi_r = diff[ry0:, rx_right:]
    if (roi_r > 20).mean() < 0.25:
        mask[ry0:, rx_right:] = (roi_r > 16).astype(np.uint8) * 255

    roi_l = diff[ry0:, :rx_left]
    if (roi_l > 20).mean() < 0.25:
        mask[ry0:, :rx_left] = (roi_l > 16).astype(np.uint8) * 255

    if mask.sum() > 0:
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.dilate(mask, kernel, iterations=2)
        out = cv2.inpaint(out, mask, 5, cv2.INPAINT_TELEA)
    return out


def find_subject_bbox(img: np.ndarray):
    """Detect subject bounding box using LAB color contrast + Sobel gradient energy."""
    h, w = img.shape[:2]
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)

    border_px = np.concatenate([
        lab[:int(h * 0.08), :, :].reshape(-1, 3),
        lab[int(h * 0.92):, :, :].reshape(-1, 3),
        lab[:, :int(w * 0.08), :].reshape(-1, 3),
        lab[:, int(w * 0.92):, :].reshape(-1, 3),
    ], axis=0)
    bg_med = np.median(border_px, axis=0)
    color_dist = np.linalg.norm(lab - bg_med, axis=2)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    grad = np.hypot(gx, gy)
    grad_smooth = cv2.GaussianBlur(grad, (31, 31), 0)

    grad_smooth[int(h * 0.85):, int(w * 0.72):] *= 0.1
    grad_smooth[int(h * 0.85):, :int(w * 0.28)] *= 0.1

    g_norm = grad_smooth / (np.percentile(grad_smooth, 99) + 1e-5)
    c_norm = color_dist / (np.percentile(color_dist, 99) + 1e-5)
    sal = np.clip(0.65 * g_norm + 0.35 * c_norm, 0, 1.5)

    yy, xx = np.mgrid[0:h, 0:w]
    cy_prior = np.exp(-0.5 * ((yy - h * 0.5) / (h * 0.38)) ** 2)
    cx_prior = np.exp(-0.5 * ((xx - w * 0.5) / (w * 0.40)) ** 2)
    sal = sal * (0.4 + 0.6 * cy_prior * cx_prior)

    thresh = np.percentile(sal, 78)
    mask = (sal >= thresh).astype(np.uint8)
    ys, xs = np.where(mask > 0)
    if len(xs) < 50:
        return int(w * 0.15), int(h * 0.15), int(w * 0.85), int(h * 0.85)
    x0, x1 = int(np.percentile(xs, 3)), int(np.percentile(xs, 97))
    y0, y1 = int(np.percentile(ys, 3)), int(np.percentile(ys, 97))
    return x0, y0, x1, y1


def extract_clean_slice(img: np.ndarray) -> np.ndarray:
    """Extract a horizontal slice containing the subject and resize to height TH=375."""
    img = heal_corner_watermarks(img)
    h, w = img.shape[:2]
    x0, y0, x1, y1 = find_subject_bbox(img)
    subj_h = max(y1 - y0, int(h * 0.35))
    subj_cy = 0.5 * (y0 + y1)

    crop_h = int(np.clip(subj_h / 0.68, h * 0.52, h * 0.96))
    cy0 = int(np.clip(subj_cy - crop_h * 0.5, 0, h - crop_h))
    cy1 = cy0 + crop_h

    cropped = img[cy0:cy1, :]
    scale = TH / float(cropped.shape[0])
    new_w = max(int(round(w * scale)), int(TH * 1.25))
    interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LANCZOS4
    return cv2.resize(cropped, (new_w, TH), interpolation=interp)


def extend_side_bokeh_smooth(edge_strip: np.ndarray, target_w: int, side: str) -> np.ndarray:
    """Create a streak-free bokeh extension of width `target_w` using 2D area-downsampling + cubic upsampling."""
    if target_w <= 0:
        return np.zeros((TH, 0, 3), dtype=np.uint8)

    src = edge_strip.astype(np.float32)
    if side == "left":
        src = src[:, ::-1, :]

    sw = src.shape[1]
    boundary = src[:, :min(24, sw), :]
    row_med = np.median(src[:, :min(12, sw), :], axis=1, keepdims=True)

    flat_px = boundary.reshape(-1, 3)
    global_med = np.median(flat_px, axis=0)
    row_dist = np.linalg.norm(row_med[:, 0, :] - global_med, axis=1)
    outlier_scale = np.percentile(row_dist, 65) + 12.0
    outlier_w = np.clip((row_dist - outlier_scale) / 30.0, 0.0, 0.88)[:, None, None]

    seam_col = np.mean(src[:, :3, :], axis=1, keepdims=True)
    clean_col = row_med * (1.0 - outlier_w) + global_med[None, None, :] * outlier_w

    prof_seam = cv2.resize(
        cv2.resize(seam_col, (1, 96), interpolation=cv2.INTER_AREA),
        (1, TH), interpolation=cv2.INTER_CUBIC
    )
    prof_near = cv2.resize(
        cv2.resize(clean_col, (1, 16), interpolation=cv2.INTER_AREA),
        (1, TH), interpolation=cv2.INTER_CUBIC
    )
    prof_mid = cv2.resize(
        cv2.resize(clean_col, (1, 5), interpolation=cv2.INTER_AREA),
        (1, TH), interpolation=cv2.INTER_CUBIC
    )
    prof_far = cv2.resize(
        cv2.resize(clean_col, (1, 2), interpolation=cv2.INTER_AREA),
        (1, TH), interpolation=cv2.INTER_CUBIC
    )

    x_px = np.arange(target_w, dtype=np.float32)[None, :, None]

    w_seam = np.exp(-x_px / 12.0)
    w_near = (1.0 - w_seam) * np.exp(-x_px / 48.0)
    w_mid = (1.0 - w_seam - w_near) * np.exp(-x_px / 140.0)
    w_far = np.clip(1.0 - w_seam - w_near - w_mid, 0.0, 1.0)

    base = (
        w_seam * prof_seam
        + w_near * prof_near
        + w_mid * prof_mid
        + w_far * prof_far
    )

    base_blurred = cv2.GaussianBlur(base, (0, 0), sigmaX=18.0, sigmaY=28.0)
    seam_lock = np.exp(-x_px / 10.0)
    base = seam_lock * base + (1.0 - seam_lock) * base_blurred

    src_low = cv2.GaussianBlur(src, (0, 0), sigmaX=12.0, sigmaY=12.0)
    residual = np.clip(src - src_low, -10.0, 10.0) * 0.45

    rng = np.random.default_rng(42 if side == "left" else 137)
    tex_canvas = np.zeros((TH, target_w, 3), dtype=np.float32)
    patch_w = min(48, sw)
    if patch_w >= 12:
        step = max(patch_w // 2, 6)
        ramp = np.linspace(0, 1, step, dtype=np.float32)[None, :, None]
        pos = 0
        while pos < target_w:
            max_x0 = max(1, sw - patch_w)
            px0 = int(rng.integers(0, max_x0))
            patch = residual[:, px0:px0 + patch_w, :].copy()
            if rng.random() > 0.5:
                patch = patch[::-1, :, :]
            if rng.random() > 0.5:
                patch = patch[:, ::-1, :]
            shift_y = int(rng.integers(-TH // 3, TH // 3))
            patch = np.roll(patch, shift_y, axis=0)

            end = min(pos + patch_w, target_w)
            cur_w = end - pos
            if pos == 0:
                tex_canvas[:, pos:end, :] = patch[:, :cur_w, :]
            else:
                ov = min(step, cur_w)
                r = ramp[:, :ov, :]
                tex_canvas[:, pos:pos + ov, :] = (
                    tex_canvas[:, pos:pos + ov, :] * (1.0 - r) + patch[:, :ov, :] * r
                )
                if cur_w > ov:
                    tex_canvas[:, pos + ov:end, :] = patch[:, ov:cur_w, :]
            pos += step

    tex_canvas = cv2.GaussianBlur(tex_canvas, (9, 9), 2.0)
    out = np.clip(base + tex_canvas, 0, 255).astype(np.uint8)

    if side == "left":
        out = out[:, ::-1, :]
    return out


def make_horizontal_bookmark_strip(img_path: Path) -> np.ndarray:
    """Build the unmasked 1499 x 375 horizontal bookmark strip from a photo."""
    img = cv2.imread(str(img_path))
    if img is None:
        raise RuntimeError(f"Cannot read image: {img_path}")

    sliced = extract_clean_slice(img)
    sh, sw = sliced.shape[:2]

    x0, _, x1, _ = find_subject_bbox(sliced)
    subj_cx = 0.5 * (x0 + x1)

    target_cx = 1025
    paste_x0 = int(round(target_cx - subj_cx))
    paste_x0 = int(np.clip(paste_x0, 520, 920))

    canvas = np.zeros((TH, TW, 3), dtype=np.uint8)

    src_x0 = 0
    dst_x0 = paste_x0
    copy_w = min(sw - src_x0, TW - dst_x0)
    canvas[:, dst_x0:dst_x0 + copy_w] = sliced[:, src_x0:src_x0 + copy_w]

    blend_w = min(84, copy_w // 3)
    left_ext_w = dst_x0 + blend_w
    left_strip = sliced[:, :min(110, sw)]
    left_ext = extend_side_bokeh_smooth(left_strip, left_ext_w, side="left")

    canvas[:, :dst_x0] = left_ext[:, :dst_x0]
    if blend_w > 0:
        t = np.linspace(0.0, 1.0, blend_w, dtype=np.float32)[None, :, None]
        alpha = 0.5 - 0.5 * np.cos(np.pi * t)
        canvas[:, dst_x0:dst_x0 + blend_w] = np.clip(
            left_ext[:, dst_x0:dst_x0 + blend_w].astype(np.float32) * (1.0 - alpha)
            + canvas[:, dst_x0:dst_x0 + blend_w].astype(np.float32) * alpha,
            0, 255
        ).astype(np.uint8)

    right_edge = dst_x0 + copy_w
    if right_edge < TW:
        r_blend_w = min(48, copy_w // 4)
        right_ext_w = (TW - right_edge) + r_blend_w
        right_strip = sliced[:, max(0, copy_w - 100):copy_w]
        right_ext = extend_side_bokeh_smooth(right_strip, right_ext_w, side="right")

        start_b = right_edge - r_blend_w
        t_r = np.linspace(0.0, 1.0, r_blend_w, dtype=np.float32)[None, :, None]
        alpha_r = 0.5 + 0.5 * np.cos(np.pi * t_r)
        canvas[:, start_b:right_edge] = np.clip(
            canvas[:, start_b:right_edge].astype(np.float32) * alpha_r
            + right_ext[:, :r_blend_w].astype(np.float32) * (1.0 - alpha_r),
            0, 255
        ).astype(np.uint8)
        canvas[:, right_edge:] = right_ext[:, r_blend_w:]

    return canvas


def warp_strip_to_bookmark_slot(horiz_strip: np.ndarray, out_w: int = SLOT_W, out_h: int = SLOT_H) -> np.ndarray:
    """Rotate 1499 x 375 strip 90 deg clockwise and warp to 251 x 941 3D bookmark perspective."""
    vert = cv2.rotate(horiz_strip, cv2.ROTATE_90_CLOCKWISE)
    vh, vw = vert.shape[:2]

    scale_x = out_w / float(SLOT_W)
    scale_y = out_h / float(SLOT_H)

    src_pts = np.float32([
        [0, 0],
        [vw - 1, 0],
        [vw - 1, vh - 1],
        [0, vh - 1],
    ])
    dst_pts = np.float32([
        [38.0 * scale_x, 0.0],
        [219.0 * scale_x, 0.0],
        [251.0 * scale_x, 941.0 * scale_y],
        [0.0, 941.0 * scale_y],
    ])
    M = cv2.getPerspectiveTransform(src_pts, dst_pts)
    return cv2.warpPerspective(
        vert, M, (out_w, out_h),
        flags=cv2.INTER_LANCZOS4,
        borderMode=cv2.BORDER_REPLICATE,
    )


def generate_bookmark_for_photo(src_path: Path, out_warped_path: Path, out_flat_path: Path = None):
    """Generate and save the 3D-warped bookmark overlay strip (and optional flat strip) for one photo."""
    horiz = make_horizontal_bookmark_strip(Path(src_path))
    if out_flat_path is not None:
        out_flat_path = Path(out_flat_path)
        out_flat_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(out_flat_path), horiz, [int(cv2.IMWRITE_JPEG_QUALITY), 90])

    warped = warp_strip_to_bookmark_slot(horiz, SLOT_W, SLOT_H)
    out_warped_path = Path(out_warped_path)
    out_warped_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_warped_path), warped, [int(cv2.IMWRITE_JPEG_QUALITY), 86])


def main():
    data = json.loads(MANIFEST.read_text())
    images = data["images"]
    updated = 0
    for img in images:
        sid = img["id"]
        rel_bm = f"/static/images/catalogue/bookmarks/{sid}.jpg"
        abs_bm = CATALOGUE_DIR / "bookmarks" / f"{sid}.jpg"
        if not abs_bm.exists():
            src_full = BASE_DIR / img["full"].lstrip("/")
            flat_out = EXTRAS_BOOKMARKS_DIR / f"{sid}.jpg" if EXTRAS_BOOKMARKS_DIR.parent.exists() else None
            generate_bookmark_for_photo(src_full, abs_bm, flat_out)
            updated += 1
        if img.get("bookmark") != rel_bm:
            img["bookmark"] = rel_bm
            updated += 1

    if updated:
        MANIFEST.write_text(json.dumps(data, indent=2) + "\n")
        print(f"Updated {updated} bookmark entries in {MANIFEST}")
    else:
        print("All manifest entries already have bookmarks.")


if __name__ == "__main__":
    main()
