/* Living-room wall mockup for Prints: places the chosen photo directly on the wall in
   room.jpg — frameless, positioned against the moulded wall panel already visible in that
   photo. Geometry and technique validated in issue #17's spike, ported in #20.

   Orientation (portrait vs landscape) is chosen per photo to match its own aspect ratio,
   the same test already used below for paper-size orientation — a photo is never
   force-cropped into the wrong shape. object-fit: cover on the <img> then does the actual
   centred crop once width/height are set to the target box. */

(function () {
  const printImg = document.getElementById("wall-print");
  const grid = document.querySelector(".catalogue-grid");
  const sizeInputs = document.querySelectorAll('input[name="size"]');
  const priceEl = document.getElementById("selected-price");
  const addBtn = document.getElementById("add-to-cart-print");
  const statusEl = document.getElementById("add-to-cart-status");

  // The moulded wall panel above the sofa in room.jpg, as % of the image's own dimensions
  // (1559x1009) — see issue #17's spike for how these were read off the photo.
  const PANEL = { x0: 13.79, x1: 82.1, y0: 1.98, y1: 51.04 };
  const PANEL_CX = (PANEL.x0 + PANEL.x1) / 2;
  const PANEL_CY = (PANEL.y0 + PANEL.y1) / 2;
  const ROOM_ASPECT = 1559 / 1009;

  // Real-world scale is an authored/tuned constant, not a measured one — same status the old
  // illustrated wall's PX_PER_CM had, just applied to a photo instead of a flat gradient.
  // Assumes the visible wall spans about 3m corner to corner.
  const ROOM_WIDTH_CM = 300;

  const SIZES_MM = JSON.parse(document.getElementById("print-sizes-data").textContent);

  let selected = { id: null, full: null, aspect: 1 };

  function currentSize() {
    const checked = document.querySelector('input[name="size"]:checked');
    return checked ? checked.value : null;
  }

  function render() {
    const size = currentSize();
    if (!size || !selected.full) return;

    const spec = SIZES_MM[size];
    const shortCm = spec.w_mm / 10;
    const longCm = spec.h_mm / 10;
    // Orient the print (portrait vs landscape) to whichever is closer to the photo's own
    // aspect ratio, rather than forcing every photo into one shape.
    const portraitAspect = shortCm / longCm;
    const landscapeAspect = longCm / shortCm;
    const usePortrait = Math.abs(portraitAspect - selected.aspect) <= Math.abs(landscapeAspect - selected.aspect);
    const wCm = usePortrait ? shortCm : longCm;
    const hCm = usePortrait ? longCm : shortCm;

    let widthPct = (wCm / ROOM_WIDTH_CM) * 100;
    let heightPct = ((hCm / ROOM_WIDTH_CM) * ROOM_ASPECT) * 100;

    // Safety clamp: at this room's scale, a large portrait print reaches the panel's height
    // limit well before landscape does (see #17/#20) — shrink proportionally rather than let
    // it spill past the photo itself. All current catalogue photos are comfortably under this
    // even at the largest size; only a future large portrait photo would ever hit it.
    const MAX_PCT = 94;
    if (widthPct > MAX_PCT || heightPct > MAX_PCT) {
      const scaleDown = Math.min(MAX_PCT / widthPct, MAX_PCT / heightPct);
      widthPct *= scaleDown;
      heightPct *= scaleDown;
    }

    printImg.style.width = `${widthPct}%`;
    printImg.style.height = `${heightPct}%`;
    printImg.style.left = `${PANEL_CX - widthPct / 2}%`;
    printImg.style.top = `${PANEL_CY - heightPct / 2}%`;
    printImg.src = selected.full;

    priceEl.textContent = `KES ${spec.price.toLocaleString()}`;
    addBtn.disabled = false;
  }

  grid.addEventListener("photo-selected", (event) => {
    const { id, full } = event.detail;
    const probe = new Image();
    probe.onload = () => {
      selected = { id, full, aspect: probe.naturalWidth / probe.naturalHeight };
      render();
    };
    probe.src = full;
  });

  sizeInputs.forEach((input) => input.addEventListener("change", render));

  addBtn.addEventListener("click", async () => {
    if (!selected.id) return;
    const size = currentSize();
    addBtn.disabled = true;
    const data = await addToCart({ type: "print", photo_id: selected.id, size });
    addBtn.disabled = false;
    statusEl.textContent = data.ok
      ? "Added to cart."
      : (data.error || "Couldn't add that to the cart — please try again.");
  });
})();
