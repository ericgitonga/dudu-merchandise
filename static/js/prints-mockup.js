/* Living-room wall mockup for Prints: sizes and positions a framed rendering of the chosen
   photo on an illustrated wall, scaled to the real physical dimensions of the selected paper
   size — so A0 visibly dwarfs A4 against the same room, not just a bigger price. */

(function () {
  const scene = document.getElementById("room-scene");
  const frame = document.getElementById("framed-print");
  const frameImg = document.getElementById("framed-print-img");
  const grid = document.querySelector(".catalogue-grid");
  const sizeInputs = document.querySelectorAll('input[name="size"]');
  const priceEl = document.getElementById("selected-price");
  const addBtn = document.getElementById("add-to-cart-print");
  const statusEl = document.getElementById("add-to-cart-status");

  // Pixels per centimetre for the illustrated room scene — tuned so A4 reads as clearly small
  // and A0 clearly dominates the same wall, per SIZES_MM below.
  const PX_PER_CM = 3.2;

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
    // Orient the frame (portrait vs landscape) to whichever is closer to the photo's own
    // aspect ratio, rather than forcing every photo into a fixed portrait frame.
    const portraitAspect = shortCm / longCm;
    const landscapeAspect = longCm / shortCm;
    const usePortrait = Math.abs(portraitAspect - selected.aspect) <= Math.abs(landscapeAspect - selected.aspect);
    const wCm = usePortrait ? shortCm : longCm;
    const hCm = usePortrait ? longCm : shortCm;

    const wPx = Math.round(wCm * PX_PER_CM);
    const hPx = Math.round(hCm * PX_PER_CM);

    frame.style.width = `${wPx}px`;
    frame.style.height = `${hPx}px`;
    frame.style.marginLeft = `${-wPx / 2}px`;
    frame.style.marginTop = `${-hPx / 2}px`;
    frameImg.src = selected.full;

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
