/* Catalogue photo grid: click a thumbnail to select it. Dispatches a "photo-selected"
   CustomEvent on the grid element with {id, thumb, full, width, height} so page-specific mockup
   scripts (prints-mockup.js, apparel-mockup.js) can react without this file knowing about them.
   width/height come from manifest.json (baked in by scripts/add_catalogue_dimensions.py, issue
   #38) rather than any live image element — mockup scripts get the aspect ratio instantly, with
   no network/image-load dependency at all.

   Selecting the first photo by default (so the mockup preview isn't blank on load) is left to
   each mockup script to trigger itself, synchronously, right after it attaches its own
   "photo-selected" listener (see prints-mockup.js/apparel-mockup.js) — not done here via a
   deferred setTimeout. A previous version called `first.click()` from a `setTimeout(..., 0)`
   here specifically to let later <script> tags attach their listener first, but headless
   Chromium's background-tab timer throttling (routine for a test harness that runs many
   sequential pages in one shared browser process, issue #44) could delay or entirely skip that
   callback, intermittently shipping a permanently-disabled add-to-cart button (issue #90). A
   synchronous call from the last script has no timer to throttle. */

document.querySelectorAll(".catalogue-grid").forEach((grid) => {
  grid.addEventListener("click", (event) => {
    const button = event.target.closest(".catalogue-thumb");
    if (!button || !grid.contains(button)) return;

    grid.querySelectorAll(".catalogue-thumb.selected").forEach((el) => el.classList.remove("selected"));
    button.classList.add("selected");

    grid.dispatchEvent(
      new CustomEvent("photo-selected", {
        detail: {
          id: button.dataset.id,
          thumb: button.dataset.thumb,
          full: button.dataset.full,
          width: Number(button.dataset.width),
          height: Number(button.dataset.height),
        },
      })
    );
  });
});
