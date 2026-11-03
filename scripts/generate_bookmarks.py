"""Generates 3D perspective-warped bookmark mockup strips (`static/images/catalogue/bookmarks/<id>.jpg`)
for the Classic Books bookmark scene (`static/images/mockup/bookmark.jpg`), and saves the upscaled
print-quality 4:1 bookmark design (`5998 x 1500` px @ 600 DPI, masked with `Bookmark Stencil 2.pdf`
at 100% opacity and trimmed tightly to the stencil bounds) to
`extras/projects/dudu-merchandise/assets/bookmarks/`.

Each photo is mapped across the full 4:1 bookmark canvas (`5998 x 1500`) directly from the
native high-resolution source photograph in `extras/projects/dudu-merchandise/assets/catalogue/`
with zero artificial left-side Gaussian blur smearing:
- When the subject fits within a 4:1 horizontal slice (`crop_h = w / 4`), a pure 1:1 isotropic
  full-width crop is used across 100% of the bookmark.
- When a taller subject requires `crop_h > w / 4`, foreground object columns (`col_obj`) are
  locked at ~1.0x isotropic aspect ratio while low-rigidity left background columns smoothly
  expand via a C1-continuous monotonic remap (`cv2.remap` with `INTER_LANCZOS4`), coupled with
  centered 2D isotropic vertical zoom when the left background is pure out-of-focus bokeh.

Can be imported by `scripts/onboard_catalogue_photos.py` or run standalone:

    conda run -n ds python scripts/generate_bookmarks.py [--force]
"""

import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

TW, TH = 1499, 375
TW_4X, TH_4X = 5998, 1500
SLOT_W, SLOT_H = 251, 941

BASE_DIR = Path(__file__).parent.parent
CATALOGUE_DIR = BASE_DIR / "static" / "images" / "catalogue"
E2E_CATALOGUE_DIR = BASE_DIR / "static" / "images" / "catalogue-e2e"
MANIFEST = CATALOGUE_DIR / "manifest.json"
E2E_MANIFEST = E2E_CATALOGUE_DIR / "manifest.json"

EXTRAS_CATALOGUE_DIR = Path("/home/gitonga/Develop/projects/extras/projects/dudu-merchandise/assets/catalogue")
EXTRAS_BOOKMARKS_DIR = Path("/home/gitonga/Develop/projects/extras/projects/dudu-merchandise/assets/bookmarks")
PERSONAL_BS_DIR = Path("/home/gitonga/Develop/projects/extras/personal/bs")
STENCIL2_PDF = Path("/home/gitonga/Downloads/Bookmark Stencil 2.pdf")

ORIGINAL_13_MANIFEST_MAP = {
    "bt-001": PERSONAL_BS_DIR / "008.jpg",
    "bt-002": PERSONAL_BS_DIR / "Woodwalker.jpg",
    "bt-014": PERSONAL_BS_DIR / "4.jpg",
}

_STENCIL_CACHE = {}


def get_stencil2_masks():
    """Return `(stencil_1x, stencil_4x)` uint8 masks (0 = inside bookmark, 255 = outside stencil)."""
    if "masks" in _STENCIL_CACHE:
        return _STENCIL_CACHE["masks"]

    cache_png = Path("/tmp/stencil2_1200-1.png")
    if not cache_png.exists() and STENCIL2_PDF.exists():
        subprocess.run(
            ["pdftoppm", "-png", "-r", "1200", str(STENCIL2_PDF), "/tmp/stencil2_1200"],
            check=True,
        )

    if cache_png.exists():
        W_1X, H_1X = 1625, 515
        s2_pil = Image.open(cache_png).convert("L").resize(
            (W_1X * 4, H_1X * 4), Image.Resampling.LANCZOS
        )
        s2_full = np.array(s2_pil)
        ys, xs = np.where(s2_full < 250)
        tx1, tx2 = int(xs.min()), int(xs.max()) + 1
        ty1, ty2 = int(ys.min()), int(ys.max()) + 1
        s2_4x = cv2.resize(
            s2_full[ty1:ty2, tx1:tx2], (TW_4X, TH_4X), interpolation=cv2.INTER_AREA
        )
    else:
        # Analytical fallback matching Bookmark Stencil 2.pdf (semicircular left cap r=750, rounded right corners r=160)
        s2_4x = np.full((TH_4X, TW_4X), 255, dtype=np.uint8)
        r_left = TH_4X // 2
        r_right = 160
        cv2.rectangle(s2_4x, (r_left, 0), (TW_4X - r_right, TH_4X), 0, -1)
        cv2.rectangle(s2_4x, (TW_4X - r_right, r_right), (TW_4X, TH_4X - r_right), 0, -1)
        cv2.circle(s2_4x, (r_left, r_left), r_left, 0, -1, lineType=cv2.LINE_AA)
        cv2.circle(s2_4x, (TW_4X - r_right, r_right), r_right, 0, -1, lineType=cv2.LINE_AA)
        cv2.circle(s2_4x, (TW_4X - r_right, TH_4X - r_right), r_right, 0, -1, lineType=cv2.LINE_AA)

    s2_1x = cv2.resize(s2_4x, (TW, TH), interpolation=cv2.INTER_AREA)
    _STENCIL_CACHE["masks"] = (s2_1x, s2_4x)
    return s2_1x, s2_4x


def unsharp_mask(img: np.ndarray, sigma: float = 1.2, strength: float = 0.32) -> np.ndarray:
    """Apply subtle unsharp masking to preserve crisp micro-detail at 4x print scale."""
    blur = cv2.GaussianBlur(img, (0, 0), sigma)
    return cv2.addWeighted(img, 1.0 + strength, blur, -strength, 0)


def heal_corner_watermarks(img: np.ndarray) -> np.ndarray:
    """Inpaint thin bottom-corner signature strokes prior to cropping so signatures are not clipped or stretched."""
    h, w = img.shape[:2]
    out = img.copy()
    for x0, x1 in [(int(w * 0.78), w), (0, int(w * 0.22))]:
        y0, y1 = int(h * 0.88), h
        roi = out[y0:y1, x0:x1]
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (21, 21), 0)
        diff = np.abs(gray.astype(np.int16) - blur.astype(np.int16))
        stroke = (diff > 14).astype(np.uint8)
        frac = stroke.mean()
        if 0.0008 < frac < 0.12:
            mask_roi = cv2.dilate(stroke * 255, np.ones((5, 5), np.uint8), iterations=2)
            out[y0:y1, x0:x1] = cv2.inpaint(roi, mask_roi, 5, cv2.INPAINT_TELEA)
    return out


def compute_saliency_maps(img: np.ndarray):
    """Compute `(vert_sal, obj_sal, det_all)` for vertical cropping and object-locked horizontal remapping."""
    h, w = img.shape[:2]
    scale = 600.0 / max(w, h)
    sh, sw = max(32, int(round(h * scale))), max(32, int(round(w * scale)))
    small = cv2.resize(img, (sw, sh), interpolation=cv2.INTER_AREA)

    lab = cv2.cvtColor(small, cv2.COLOR_BGR2LAB).astype(np.float32)
    all_border = np.concatenate([
        lab[:max(2, int(sh * 0.06)), :, :].reshape(-1, 3),
        lab[int(sh * 0.94):, :, :].reshape(-1, 3),
        lab[:, :max(2, int(sw * 0.06)), :].reshape(-1, 3),
        lab[:, int(sw * 0.94):, :].reshape(-1, 3),
    ], axis=0)
    bg_all_med = np.median(all_border, axis=0)
    color_dist_all = np.linalg.norm(lab - bg_all_med, axis=2)

    left_w = max(3, int(sw * 0.08))
    left_strip = lab[:, :left_w, :]
    left_profile = np.median(left_strip, axis=1)
    idx_pal = np.linspace(0, sh - 1, min(sh, 36)).astype(np.int32)
    palette = left_profile[idx_pal]
    palette_dist = np.linalg.norm(lab[:, :, None, :] - palette[None, None, :, :], axis=3).min(axis=2)
    left_self_noise = float(np.percentile(palette_dist[:, :left_w], 98.5))
    color_dist_left = np.maximum(0.0, palette_dist - left_self_noise * 1.10)

    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY).astype(np.float32)
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    grad = np.hypot(gx, gy)
    lap = np.abs(cv2.Laplacian(gray, cv2.CV_32F, ksize=3))
    l_mean = cv2.GaussianBlur(gray, (15, 15), 0)
    l_sq = cv2.GaussianBlur(gray ** 2, (15, 15), 0)
    local_std = np.sqrt(np.maximum(0.0, l_sq - l_mean ** 2))

    vert_detail = cv2.GaussianBlur(0.55 * grad + 0.45 * lap, (15, 15), 0)
    vert_detail[int(sh * 0.90):, int(sw * 0.80):] *= 0.05
    vert_detail[int(sh * 0.90):, :int(sw * 0.20)] *= 0.05

    obj_detail = cv2.GaussianBlur(0.35 * grad + 0.25 * lap + 0.40 * local_std, (15, 15), 0)
    obj_detail[int(sh * 0.90):, int(sw * 0.80):] *= 0.05
    obj_detail[int(sh * 0.90):, :int(sw * 0.20)] *= 0.05

    left_det_max = float(np.percentile(obj_detail[:, :max(3, int(sw * 0.10))], 99.5))
    detail_excess = np.maximum(0.0, obj_detail - left_det_max * 1.02)

    d_all_norm = np.clip(vert_detail / (np.percentile(vert_detail, 99) + 1e-5), 0.0, 1.3)
    c_all_norm = np.clip(color_dist_all / (np.percentile(color_dist_all, 99) + 1e-5), 0.0, 1.3)

    d_left_norm = np.clip(detail_excess / (np.percentile(detail_excess, 99.5) + 15.0), 0.0, 1.2)
    c_left_norm = np.clip(color_dist_left / (np.percentile(color_dist_left, 99.0) + 12.0), 0.0, 1.2)

    yy, xx = np.mgrid[0:sh, 0:sw]
    cy_prior = np.exp(-0.5 * ((yy - sh * 0.5) / (sh * 0.40)) ** 2)
    cx_prior = np.exp(-0.5 * ((xx - sw * 0.52) / (sw * 0.38)) ** 2)

    vert_sal = np.clip((0.72 * d_all_norm + 0.28 * c_all_norm) * (0.20 + 0.80 * cy_prior * cx_prior), 0.0, 1.0)
    obj_sal = np.clip(np.maximum(d_left_norm, c_left_norm), 0.0, 1.0)
    obj_sal[int(sh * 0.90):, int(sw * 0.80):] *= 0.1
    obj_sal[int(sh * 0.90):, :int(sw * 0.20)] *= 0.1
    obj_sal[:, :left_w] = 0.0

    return (
        cv2.resize(vert_sal, (w, h), interpolation=cv2.INTER_LINEAR),
        cv2.resize(obj_sal, (w, h), interpolation=cv2.INTER_LINEAR),
        cv2.resize(d_all_norm, (w, h), interpolation=cv2.INTER_LINEAR),
    )


def add_micro_grain_if_stretched(horiz_4x: np.ndarray, stretch_1d: np.ndarray, cropped: np.ndarray) -> np.ndarray:
    """Restore subtle native sensor micro-grain in regions where smooth background bokeh expands > 1.35x."""
    max_s = float(stretch_1d.max())
    if max_s <= 1.35:
        return horiz_4x
    gray = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY).astype(np.float32)
    hp = gray - cv2.GaussianBlur(gray, (5, 5), 0)
    noise_std = float(np.clip(np.percentile(np.abs(hp), 30) * 1.4826, 0.6, 3.0))
    rng = np.random.default_rng(42)
    grain = rng.normal(0.0, noise_std, (TH_4X, TW_4X)).astype(np.float32)
    grain = cv2.GaussianBlur(grain, (3, 3), 0.65)[:, :, None]
    weight = np.clip((stretch_1d - 1.25) / 1.5, 0.0, 0.80)[None, :, None]
    return np.clip(horiz_4x.astype(np.float32) + grain * weight, 0, 255).astype(np.uint8)


def build_bookmark_strips(img_path: Path):
    """Build both the unmasked `1499 x 375` strip (for 3D mockup warping) and the upscaled,
    Stencil-2-masked `5998 x 1500` print strip directly from the highest-resolution source image
    with a full-image, unblurred composition across the entire 4:1 bookmark.
    """
    raw = cv2.imread(str(img_path))
    if raw is None:
        raise RuntimeError(f"Cannot read image: {img_path}")

    img = heal_corner_watermarks(raw)
    h, w = img.shape[:2]
    vert_sal, obj_sal, det_all = compute_saliency_maps(img)

    thresh = np.percentile(vert_sal, 85)
    ys, xs = np.where(vert_sal >= thresh)
    if len(xs) < 50:
        x0, y0, x1, y1 = int(w * 0.2), int(h * 0.2), int(w * 0.85), int(h * 0.8)
    else:
        x0, x1 = int(np.percentile(xs, 3)), int(np.percentile(xs, 97))
        y0, y1 = int(np.percentile(ys, 1.5)), int(np.percentile(ys, 98.5))

    rh_ys, rh_xs = np.where(vert_sal[:, int(w * 0.25):] >= thresh)
    if len(rh_ys) >= 50:
        ry0, ry1 = int(np.percentile(rh_ys, 1.0)), int(np.percentile(rh_ys, 99.0))
        if y0 < int(h * 0.06) and ry0 > y0 + int(h * 0.08):
            y0 = ry0
        y1 = max(y1, ry1)

    subj_h = y1 - y0
    weights = np.maximum(0.0, vert_sal[:, int(w * 0.20):] - np.percentile(vert_sal, 76))
    if weights.sum() > 0:
        yy_grid = np.arange(h, dtype=np.float32)[:, None]
        subj_cy = float((weights * yy_grid).sum() / weights.sum())
    else:
        subj_cy = 0.5 * (y0 + y1)
    subj_cy = 0.5 * (0.5 * (y0 + y1)) + 0.5 * subj_cy

    h_4to1 = w * (TH_4X / float(TW_4X))
    max_h_cap = h * 0.82 if subj_h > h * 0.62 else h * 0.72
    crop_h = int(round(np.clip(max(h_4to1, subj_h / 0.86), h_4to1, min(h, max_h_cap))))
    cy0 = int(np.clip(round(subj_cy - crop_h * 0.5), 0, h - crop_h))
    if y0 < cy0 and y1 <= cy0 + crop_h:
        cy0 = max(0, min(y0 - int(crop_h * 0.04), h - crop_h))
    elif y1 > cy0 + crop_h and y0 >= cy0:
        cy0 = max(0, min(y1 - crop_h + int(crop_h * 0.04), h - crop_h))

    right_space = w - x1
    max_right_space = int(w * 0.14)
    trim_r = 0
    if right_space > max_right_space:
        trim_r = min(right_space - max_right_space, int(w * 0.18))
    wc = w - trim_r

    cropped = img[cy0:cy0 + crop_h, :wc]
    obj_crop = obj_sal[cy0:cy0 + crop_h, :wc]
    vert_crop = vert_sal[cy0:cy0 + crop_h, :wc]
    det_crop = det_all[cy0:cy0 + crop_h, :wc]

    scale_y = TH_4X / float(crop_h)
    iso_w = wc * scale_y

    if iso_w >= TW_4X:
        resized = cv2.resize(cropped, (int(round(iso_w)), TH_4X), interpolation=cv2.INTER_LANCZOS4)
        start_x = max(0, min(resized.shape[1] - TW_4X, int(round(x0 * scale_y - TW_4X * 0.35))))
        horiz_4x = resized[:, start_x:start_x + TW_4X].copy()
    else:
        col_obj = np.maximum(
            np.percentile(obj_crop, 98.5, axis=0),
            np.percentile(vert_crop, 96.0, axis=0),
        ).astype(np.float32)
        dil_w = max(5, int(round(wc * 0.035)) | 1)
        col_obj = cv2.dilate(col_obj[None, :], np.ones((1, dil_w), np.uint8))[0]
        col_obj = np.clip(col_obj / (max(0.35, float(np.percentile(col_obj, 85))) + 1e-5), 0.0, 1.0)
        col_obj = np.where(col_obj >= 0.38, 1.0, col_obj / 0.38).astype(np.float32)

        active_cols = np.where(col_obj >= 0.55)[0]
        if len(active_cols) >= 10:
            s_x0 = int(np.percentile(active_cols, 2))
            s_x1 = int(np.percentile(active_cols, 98))
            lock_start = max(int(wc * 0.12), s_x0)
            if lock_start < s_x1:
                col_obj[lock_start:s_x1] = np.maximum(col_obj[lock_start:s_x1], 0.90)

        col_obj = cv2.GaussianBlur(col_obj[None, :], (0, 0), sigmaX=max(10.0, wc * 0.04))[0]

        xx_norm = np.linspace(0.0, 1.0, wc, dtype=np.float32)
        left_bias = np.where(xx_norm < 0.65, 1.35 - 0.55 * xx_norm, 0.22 * (1.0 - xx_norm)).astype(np.float32)
        flexibility = ((np.maximum(0.01, 1.0 - 0.97 * col_obj)) ** 2.4) * left_bias
        flexibility = cv2.GaussianBlur(flexibility[None, :], (0, 0), sigmaX=max(16.0, wc * 0.06))[0]
        flexibility = np.maximum(flexibility, 1e-4)

        extra_w = float(TW_4X) - iso_w
        col_widths = scale_y + extra_w * (flexibility / flexibility.sum())

        col_tex = cv2.GaussianBlur(np.percentile(det_crop, 80, axis=0)[None, :].astype(np.float32), (0, 0), sigmaX=max(10.0, wc * 0.04))[0]
        max_mult = np.where(col_tex < 0.24, 3.6, 2.45 + 1.15 * np.maximum(0.0, (0.24 - col_tex) / 0.24)).astype(np.float32)
        max_mult = np.where(col_obj > 0.55, np.minimum(max_mult, 1.06), max_mult)
        max_mult = np.where(xx_norm > 0.72, np.minimum(max_mult, 1.30), max_mult)
        max_col_w = max_mult * scale_y

        for _ in range(6):
            excess = np.maximum(0.0, col_widths - max_col_w)
            if excess.sum() < 0.5:
                break
            col_widths = np.minimum(col_widths, max_col_w)
            free = (col_widths < max_col_w).astype(np.float32) * np.where(col_obj > 0.55, 0.0, flexibility + 0.02)
            if free.sum() > 0:
                col_widths += excess.sum() * (free / free.sum())
            else:
                bg_free = (col_widths < max_col_w * 1.15).astype(np.float32) * np.where(
                    xx_norm > 0.75, 0.0, np.maximum(0.05, 1.0 - 0.85 * col_obj) * left_bias
                )
                if bg_free.sum() > 0:
                    col_widths += excess.sum() * (bg_free / bg_free.sum())
                else:
                    col_widths += excess.sum() / float(wc)

        col_widths = cv2.GaussianBlur(col_widths[None, :], (0, 0), sigmaX=max(12.0, wc * 0.045))[0]
        col_widths *= float(TW_4X) / col_widths.sum()

        cum_x = np.concatenate([[0.0], np.cumsum(col_widths)])
        cum_x[-1] = float(TW_4X)
        dst_x = np.arange(TW_4X, dtype=np.float32) + 0.5
        src_x_1d = np.interp(dst_x, cum_x, np.arange(wc + 1, dtype=np.float32)) - 0.5
        src_x_1d = np.clip(src_x_1d, 0.0, wc - 1.0).astype(np.float32)

        ds_dx = np.gradient(src_x_1d) * scale_y
        stretch_1d = np.clip(1.0 / np.maximum(ds_dx, 0.12), 1.0, 5.0).astype(np.float32)

        left_25_det = float(np.percentile(det_crop[:, :max(5, int(wc * 0.25))], 90))
        if left_25_det < 0.28 and float(stretch_1d[:int(TW_4X * 0.4)].max()) > 1.85:
            bokeh_factor = np.clip((0.28 - left_25_det) / 0.18, 0.0, 1.0)
            eff_r = cv2.GaussianBlur(stretch_1d[None, :], (0, 0), sigmaX=140.0)[0]
            win_h = np.maximum(h * 0.25, crop_h / (eff_r ** (0.72 * bokeh_factor))).astype(np.float32)
            win_cy = cy0 + 0.5 * crop_h
            t_y = (np.arange(TH_4X, dtype=np.float32) + 0.5) / float(TH_4X) - 0.5
            map_y = np.clip(win_cy + t_y[:, None] * win_h[None, :], 0.0, h - 1.0).astype(np.float32)
            map_x = np.broadcast_to(src_x_1d[None, :], (TH_4X, TW_4X))
            horiz_4x = cv2.remap(img[:, :wc], map_x, map_y, interpolation=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REPLICATE)
        else:
            vert_4x = cv2.resize(cropped, (wc, TH_4X), interpolation=cv2.INTER_LANCZOS4)
            map_x = np.broadcast_to(src_x_1d[None, :], (TH_4X, TW_4X))
            map_y = np.broadcast_to(np.arange(TH_4X, dtype=np.float32)[:, None], (TH_4X, TW_4X))
            horiz_4x = cv2.remap(vert_4x, map_x, map_y, interpolation=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REPLICATE)

        horiz_4x = add_micro_grain_if_stretched(horiz_4x, stretch_1d, cropped)

    horiz_4x = unsharp_mask(horiz_4x, sigma=1.2, strength=0.32)
    horiz_1x = cv2.resize(horiz_4x, (TW, TH), interpolation=cv2.INTER_AREA)

    _, s2_4x = get_stencil2_masks()
    s_alpha_4x = (s2_4x.astype(np.float32) / 255.0)[:, :, None]
    masked_4x = np.clip(
        horiz_4x.astype(np.float32) * (1.0 - s_alpha_4x) + 255.0 * s_alpha_4x,
        0, 255,
    ).astype(np.uint8)

    return horiz_1x, masked_4x


def make_horizontal_bookmark_strip(img_path: Path) -> np.ndarray:
    """Build the unmasked 1499 x 375 horizontal bookmark strip from a photo."""
    horiz_1x, _ = build_bookmark_strips(Path(img_path))
    return horiz_1x


def warp_strip_to_bookmark_slot(horiz_strip: np.ndarray, out_w: int = SLOT_W, out_h: int = SLOT_H) -> np.ndarray:
    """Rotate horizontal strip 90 deg clockwise and warp to 251 x 941 3D bookmark perspective."""
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


def save_print_jpeg_600dpi(bgr_img: np.ndarray, out_path: Path, quality: int = 96):
    """Save a BGR image as a 600-DPI, 4:4:4 (`subsampling=0`) print-quality JPEG."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pil_im = Image.fromarray(cv2.cvtColor(bgr_img, cv2.COLOR_BGR2RGB))
    pil_im.save(str(out_path), format="JPEG", quality=quality, subsampling=0, dpi=(600, 600))


def generate_bookmark_for_photo(src_path: Path, out_warped_path: Path, out_flat_path: Path = None):
    """Generate and save the 3D-warped bookmark overlay strip and optional 5998x1500 @ 600 DPI print file."""
    src_path = Path(src_path)
    sid = out_warped_path.stem

    if sid in ORIGINAL_13_MANIFEST_MAP and ORIGINAL_13_MANIFEST_MAP[sid].exists():
        bs_master = ORIGINAL_13_MANIFEST_MAP[sid]
        if out_flat_path is not None:
            out_flat_path = Path(out_flat_path)
            out_flat_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(bs_master, out_flat_path)
        master_bgr = cv2.imread(str(bs_master))
        horiz_1x = cv2.resize(master_bgr, (TW, TH), interpolation=cv2.INTER_AREA)
    else:
        horiz_1x, masked_4x = build_bookmark_strips(src_path)
        if out_flat_path is not None:
            save_print_jpeg_600dpi(masked_4x, Path(out_flat_path), quality=96)

    warped = warp_strip_to_bookmark_slot(horiz_1x, SLOT_W, SLOT_H)
    out_warped_path = Path(out_warped_path)
    out_warped_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_warped_path), warped, [int(cv2.IMWRITE_JPEG_QUALITY), 86])


def _worker_task(task):
    sid, src_path_str, abs_bm_str, flat_out_str = task
    generate_bookmark_for_photo(
        Path(src_path_str),
        Path(abs_bm_str),
        Path(flat_out_str) if flat_out_str else None,
    )
    return sid


def resolve_highres_source(img_entry: dict) -> Path:
    """Prefer the full-resolution source photo in `extras/projects/dudu-merchandise/assets/catalogue/`."""
    sid = img_entry["id"]
    cat = img_entry.get("category", "")
    if cat and EXTRAS_CATALOGUE_DIR.exists():
        cand = EXTRAS_CATALOGUE_DIR / cat / f"{sid}.jpg"
        if cand.exists():
            return cand
    return BASE_DIR / img_entry["full"].lstrip("/")


def main():
    force = "--force" in sys.argv
    get_stencil2_masks()

    data = json.loads(MANIFEST.read_text())
    images = data["images"]
    tasks = []
    manifest_updated = 0

    for img in images:
        sid = img["id"]
        rel_bm = f"/static/images/catalogue/bookmarks/{sid}.jpg"
        abs_bm = CATALOGUE_DIR / "bookmarks" / f"{sid}.jpg"
        flat_out = EXTRAS_BOOKMARKS_DIR / f"{sid}.jpg" if EXTRAS_BOOKMARKS_DIR.parent.exists() else None

        need_gen = force or not abs_bm.exists() or (flat_out is not None and not flat_out.exists())
        if need_gen:
            src_full = resolve_highres_source(img)
            tasks.append((sid, str(src_full), str(abs_bm), str(flat_out) if flat_out else None))

        if img.get("bookmark") != rel_bm:
            img["bookmark"] = rel_bm
            manifest_updated += 1

    if E2E_MANIFEST.exists():
        e2e_data = json.loads(E2E_MANIFEST.read_text())
        seen_e2e = set()
        for img in e2e_data.get("images", []):
            stem = Path(img["full"]).stem
            if stem in seen_e2e:
                continue
            seen_e2e.add(stem)
            abs_e2e = E2E_CATALOGUE_DIR / "bookmarks" / f"{stem}.jpg"
            if force or not abs_e2e.exists():
                src_e2e = BASE_DIR / img["full"].lstrip("/")
                tasks.append((f"e2e:{stem}", str(src_e2e), str(abs_e2e), None))

    if tasks:
        t0 = time.time()
        workers = min(os.cpu_count() or 4, 8)
        print(f"Generating {len(tasks)} bookmark designs (5998x1500 @ 600 DPI + 3D web overlays) using {workers} workers...")
        done = 0
        with ProcessPoolExecutor(max_workers=workers) as ex:
            futures = [ex.submit(_worker_task, t) for t in tasks]
            for fut in as_completed(futures):
                fut.result()
                done += 1
                if done % 100 == 0 or done == len(tasks):
                    print(f"  [{done}/{len(tasks)}] completed in {time.time() - t0:.1f}s")

    if manifest_updated:
        MANIFEST.write_text(json.dumps(data, indent=2) + "\n")
        print(f"Updated {manifest_updated} bookmark entries in {MANIFEST}")
    elif not tasks:
        print("All manifest entries already have bookmarks.")


if __name__ == "__main__":
    main()
