/* Cart page: remove-item buttons, and the checkout modal that overlays the page. */

(function () {
  document.querySelectorAll(".cart-remove").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const idx = btn.dataset.index;
      const resp = await fetch(`/cart/remove/${idx}`, {
        method: "POST",
        headers: { "X-CSRFToken": csrfToken() },
      });
      const data = await resp.json().catch(() => ({}));
      if (data.ok) window.location.reload();
    });
  });

  document.querySelectorAll(".cart-qty-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      btn.disabled = true;
      const { ok } = await postJSON(`/cart/qty/${btn.dataset.index}`, {
        delta: parseInt(btn.dataset.delta, 10),
      });
      if (ok) window.location.reload();
      else btn.disabled = false;
    });
  });

  const openBtn = document.getElementById("open-checkout");
  const modal = document.getElementById("checkout-modal");
  const closeBtn = document.getElementById("close-checkout");
  const form = document.getElementById("checkout-form");
  const submitBtn = document.getElementById("checkout-submit");
  const errorEl = document.getElementById("checkout-error");
  const successEl = document.getElementById("checkout-success");
  const backToShopLink = successEl.querySelector("a");

  if (!openBtn) return; // empty cart — no checkout button rendered

  // Set once the order actually submits — checkout_submit clears the server-side cart on
  // success (app.py), but this page's own cart list/Checkout button were rendered before that
  // and don't reflect it without a reload. Closing the modal after success (the X, or clicking
  // the backdrop) needs to leave this stale page the same way "Back to shop" already does,
  // rather than just hiding the modal and stranding the user on it.
  let orderSubmitted = false;

  function openModal() {
    modal.hidden = false;
  }
  function closeModal() {
    if (orderSubmitted) {
      window.location.href = backToShopLink.href;
      return;
    }
    modal.hidden = true;
  }

  openBtn.addEventListener("click", openModal);
  closeBtn.addEventListener("click", closeModal);
  modal.addEventListener("click", (event) => {
    if (event.target === modal) closeModal();
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    errorEl.hidden = true;
    submitBtn.disabled = true;

    const payload = {
      mpesa_code: form.mpesa_code.value.trim(),
      name: form.name.value.trim(),
      contact: form.contact.value.trim(),
      location: form.location.value.trim(),
      notes: form.notes.value.trim(),
    };

    const { ok, data } = await postJSON("/api/checkout/submit", payload);
    submitBtn.disabled = false;

    if (!ok) {
      errorEl.textContent = data.error || "Something went wrong — please try again.";
      errorEl.hidden = false;
      return;
    }

    orderSubmitted = true;
    form.hidden = true;
    successEl.hidden = false;
    updateCartBadge(0);
  });
})();
