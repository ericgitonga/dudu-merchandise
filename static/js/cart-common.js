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
