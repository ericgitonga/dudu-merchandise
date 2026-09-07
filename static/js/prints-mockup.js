/* Living-room wall mockup for Prints: places the chosen photo directly on the wall in
   room.jpg — frameless, positioned against the moulded wall panel already visible in that
   photo. Geometry and technique validated in issue #17's spike, ported in #20.

   The mockup always renders at A2, regardless of which size is selected for ordering — sizing
   the box to match every ISO size in turn made the larger/smaller ends look disproportionate
   against this one room photo (A0 in particular read as roughly couch-sized, which it isn't;
   see issue #25). A2 is the one that reads right, so it's the fixed reference render; the size
   picker only ever changes price and what's ordered, never the preview's own dimensions.

   Orientation (portrait vs landscape) is still chosen per photo to match its own aspect ratio —
   the same test already used below for paper-size orientation — so a photo is never
   force-cropped into the wrong shape. object-fit: cover then does the actual centred crop once
   width/height are set to the target box. */

(function () {
  const printImg = document.getElementById("wall-print");
  const grid = document.querySelector(".catalogue-grid");
  const sizeInputs = document.querySelectorAll('input[name="size"]');
  const priceEl = document.getElementById("selected-price");
  const addBtn = document.getElementById("add-to-cart-print");
  const statusEl = document.getElementById("add-to-cart-status");

  // The moulded wall panel above the sofa in room.jpg, as % of the image's own dimensions
  // (read off the original 1559x1009 source — percentages, so this held when the shipped
  // file was later downsized to 1100x712 for load time) — see issue #17's spike.
  const PANEL = { x0: 13.79, x1: 82.1, y0: 1.98, y1: 51.04 };
  const PANEL_CX = (PANEL.x0 + PANEL.x1) / 2;
  const PANEL_CY = (PANEL.y0 + PANEL.y1) / 2;
  const ROOM_ASPECT = 1100 / 712;

  // Real-world scale is an authored/tuned constant, not a measured one — same status the old
  // illustrated wall's PX_PER_CM always had. Assumes the visible wall spans about 3m corner
  // to corner. Only matters for the one fixed A2 render now, not for comparing sizes.
  const ROOM_WIDTH_CM = 300;
  const MOCKUP_SIZE = "A2";

  const SIZES_MM = JSON.parse(document.getElementById("print-sizes-data").textContent);

  let selected = { id: null, full: null, aspect: 1 };

  function currentSize() {
    const checked = document.querySelector('input[name="size"]:checked');
    return checked ? checked.value : null;
  }

  function renderMockup() {
    if (!selected.full) return;

    const spec = SIZES_MM[MOCKUP_SIZE];
    const shortCm = spec.w_mm / 10;
    const longCm = spec.h_mm / 10;
    // Orient the print (portrait vs landscape) to whichever is closer to the photo's own
    // aspect ratio, rather than forcing every photo into one shape.
    const portraitAspect = shortCm / longCm;
    const landscapeAspect = longCm / shortCm;
    const usePortrait = Math.abs(portraitAspect - selected.aspect) <= Math.abs(landscapeAspect - selected.aspect);
    const wCm = usePortrait ? shortCm : longCm;
    const hCm = usePortrait ? longCm : shortCm;

    const widthPct = (wCm / ROOM_WIDTH_CM) * 100;
    const heightPct = (hCm / ROOM_WIDTH_CM) * ROOM_ASPECT * 100;

    printImg.style.width = `${widthPct}%`;
    printImg.style.height = `${heightPct}%`;
    printImg.style.left = `${PANEL_CX - widthPct / 2}%`;
    printImg.style.top = `${PANEL_CY - heightPct / 2}%`;
    printImg.src = selected.full;
  }

  function updateOrderControls() {
    const size = currentSize();
    if (!size) return;
    priceEl.textContent = `KES ${SIZES_MM[size].price.toLocaleString()}`;
    addBtn.disabled = !selected.id;
  }

  grid.addEventListener("photo-selected", (event) => {
    const { id, full, thumbImg } = event.detail;

    function useThumb() {
      selected = { id, full, aspect: thumbImg.naturalWidth / thumbImg.naturalHeight };
      renderMockup();
      updateOrderControls();
    }

    // The thumbnail shares the full photo's aspect ratio and is already on screen — read its
    // dimensions instead of fetching the full-resolution image a second time just to probe its
    // size. Only wait on its own load if the auto-selected-first-photo path beat the thumbnail
    // to it (issue #30: the redundant full-image fetch competed with the room mockup photo and
    // every other thumbnail for the dev server's attention, occasionally blowing e2e's wait
    // budget in CI).
    if (thumbImg.complete && thumbImg.naturalWidth > 0) {
      useThumb();
    } else {
      thumbImg.addEventListener("load", useThumb, { once: true });
    }
  });

  sizeInputs.forEach((input) => input.addEventListener("change", updateOrderControls));

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
