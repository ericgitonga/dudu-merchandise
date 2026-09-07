/* Shared helpers used on every page: CSRF-aware POSTs and the cart badge. */

function csrfToken() {
  const meta = document.querySelector('meta[name="csrf-token"]');
  return meta ? meta.content : "";
}

async function postJSON(url, body) {
  const resp = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": csrfToken(),
    },
    body: JSON.stringify(body || {}),
  });
  const data = await resp.json().catch(() => ({}));
  return { ok: resp.ok && data.ok !== false, status: resp.status, data };
}

function updateCartBadge(count) {
  const badge = document.getElementById("cart-badge");
  if (badge) badge.textContent = String(count);
}

/* Quantity stepper used on the Prints/Apparel selection panes (.qty-stepper, local only — the
   chosen value is read when "Add to cart" is clicked). Distinct from the cart page's own
   +/- buttons (.cart-qty-btn, wired in checkout.js), which call the server directly. */
document.querySelectorAll(".qty-stepper").forEach((stepper) => {
  const input = stepper.querySelector(".qty-input");
  if (!input) return;
  const min = parseInt(input.min, 10) || 1;
  const max = parseInt(input.max, 10) || Infinity;

  function clamp() {
    let val = parseInt(input.value, 10);
    if (Number.isNaN(val)) val = min;
    input.value = Math.min(max, Math.max(min, val));
  }

  stepper.querySelectorAll(".qty-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const step = parseInt(btn.dataset.step, 10) || 0;
      input.value = (parseInt(input.value, 10) || min) + step;
      clamp();
    });
  });
  input.addEventListener("change", clamp);
});

async function addToCart(fields) {
  const params = new URLSearchParams(fields);
  const resp = await fetch("/cart/add", {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
      "X-CSRFToken": csrfToken(),
    },
    body: params.toString(),
  });
  const data = await resp.json().catch(() => ({}));
  if (data.ok) updateCartBadge(data.cart_count);
  return data;
}
