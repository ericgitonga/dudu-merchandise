/* Below the 800px breakpoint (style.css), the sidebar's category list and the size radios are
   replaced visually by two <select>s — the catalogue grid reflows into a horizontal strip and
   this filters it to the chosen category by toggling `hidden` on the same catalogue-thumb
   elements the desktop grid renders, and the size select just drives the real "size" radio
   group so prints-mockup.js's existing listener doesn't need to know a select exists. Neither
   select duplicates any state — there's nothing here to keep in sync when the viewport crosses
   the breakpoint. */

(function () {
  const categorySelect = document.getElementById("mobile-category-select");
  const grid = document.querySelector(".catalogue-grid");
  if (categorySelect && grid) {
    const applyFilter = () => {
      grid.querySelectorAll(".catalogue-thumb").forEach((thumb) => {
        thumb.hidden = thumb.dataset.category !== categorySelect.value;
      });
    };
    categorySelect.addEventListener("change", applyFilter);
    applyFilter();
  }

  const sizeSelect = document.getElementById("mobile-size-select");
  if (sizeSelect) {
    sizeSelect.addEventListener("change", () => {
      const radio = document.querySelector(`input[name="size"][value="${sizeSelect.value}"]`);
      if (radio) {
        radio.checked = true;
        radio.dispatchEvent(new Event("change", { bubbles: true }));
      }
    });
  }
})();
