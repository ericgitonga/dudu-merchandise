/* T-shirt mockup: same shirt silhouette/chest-placement geometry as merch-mockup's own
   _make_mockup (SHIRT_PTS / NECK / CHEST_W / CHEST_Y), redrawn here as SVG instead of Pillow —
   folded into this site as a page rather than calling out to the standalone merch-mockup app. */

(function () {
  const shirtBody = document.getElementById("shirt-body");
  const designImg = document.getElementById("shirt-design");
  const grid = document.querySelector(".catalogue-grid");
  const swatches = document.querySelectorAll(".shirt-swatch");
  const ageInputs = document.querySelectorAll('input[name="age_group"]');
  const colourInput = document.getElementById("selected-shirt-colour");
  const priceEl = document.getElementById("selected-price");
  const addBtn = document.getElementById("add-to-cart-apparel");
  const statusEl = document.getElementById("add-to-cart-status");

  const CHEST_W = 375;
  const CHEST_Y = 280;
  const CHEST_X = (1000 - CHEST_W) / 2;

  const PRICES = JSON.parse(document.getElementById("apparel-prices-data").textContent);

  let selected = { id: null, full: null };

  function currentAgeGroup() {
    const checked = document.querySelector('input[name="age_group"]:checked');
    return checked ? checked.value : "adult";
  }

  function updatePrice() {
    priceEl.textContent = `KES ${PRICES[currentAgeGroup()].toLocaleString()}`;
  }

  grid.addEventListener("photo-selected", (event) => {
    const { id, full, thumbImg } = event.detail;

    function useThumb() {
      selected = { id, full };
      const h = CHEST_W * (thumbImg.naturalHeight / thumbImg.naturalWidth);
      designImg.setAttribute("href", full);
      designImg.setAttribute("x", CHEST_X);
      designImg.setAttribute("y", CHEST_Y);
      designImg.setAttribute("width", CHEST_W);
      designImg.setAttribute("height", h);
      addBtn.disabled = false;
    }

    // Same fix as prints-mockup.js (issue #30): read the aspect ratio off the already-loaded
    // thumbnail instead of fetching the full-resolution image a second time just to probe it.
    if (thumbImg.complete && thumbImg.naturalWidth > 0) {
      useThumb();
    } else {
      thumbImg.addEventListener("load", useThumb, { once: true });
    }
  });

  swatches.forEach((swatch) => {
    swatch.addEventListener("click", () => {
      swatches.forEach((s) => s.classList.remove("selected"));
      swatch.classList.add("selected");
      const hex = swatch.dataset.hex;
      const name = swatch.dataset.name;
      shirtBody.setAttribute("fill", hex);
      colourInput.value = name;
    });
  });

  ageInputs.forEach((input) => input.addEventListener("change", updatePrice));
  updatePrice();

  addBtn.addEventListener("click", async () => {
    if (!selected.id) return;
    addBtn.disabled = true;
    const data = await addToCart({
      type: "apparel",
      photo_id: selected.id,
      age_group: currentAgeGroup(),
      shirt_colour: colourInput.value,
    });
    addBtn.disabled = false;
    statusEl.textContent = data.ok
      ? "Added to cart."
      : (data.error || "Couldn't add that to the cart — please try again.");
  });
})();
