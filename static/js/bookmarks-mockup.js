/* Bookmarks mockup and cart addition handler for /bookmarks */

(function () {
  const bookmarkImg = document.getElementById("bookmark-img");
  const grid = document.querySelector(".catalogue-grid");
  const priceEl = document.getElementById("selected-price");
  const addBtn = document.getElementById("add-to-cart-bookmark");
  const statusEl = document.getElementById("add-to-cart-status");
  const qtyInput = document.getElementById("selected-qty");
  const unitPrice = Number(document.getElementById("bookmark-price-data").textContent) || 1500;

  let selected = { id: null, bookmark: null };

  function currentQty() {
    return parseInt(qtyInput.value, 10) || 1;
  }

  function updateOrderControls() {
    const qty = currentQty();
    priceEl.textContent = qty > 1
      ? "KES " + unitPrice.toLocaleString() + " each — KES " + (unitPrice * qty).toLocaleString() + " total"
      : "KES " + unitPrice.toLocaleString();
    addBtn.disabled = !selected.id;
  }

  grid.addEventListener("photo-selected", (event) => {
    const { id, bookmark } = event.detail;
    selected = { id, bookmark };
    if (bookmark) {
      bookmarkImg.src = bookmark;
    }
    updateOrderControls();
  });

  const firstThumb = grid.querySelector(".catalogue-thumb");
  if (firstThumb) firstThumb.click();

  qtyInput.addEventListener("input", updateOrderControls);
  qtyInput.addEventListener("change", updateOrderControls);

  addBtn.addEventListener("click", async () => {
    if (!selected.id) return;
    const qty = currentQty();
    addBtn.disabled = true;
    const data = await addToCart({ type: "print", photo_id: selected.id, size: "Bookmark", qty });
    addBtn.disabled = false;
    statusEl.textContent = data.ok
      ? (qty === 1 ? "Added to cart." : "Added " + qty + " to cart.")
      : (data.error || "Couldn't add that to the cart — please try again.");
    if (data.ok) {
      qtyInput.value = 1;
      updateOrderControls();
    }
  });
})();
