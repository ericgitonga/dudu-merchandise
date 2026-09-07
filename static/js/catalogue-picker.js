/* Catalogue photo grid: click a thumbnail to select it. Dispatches a "photo-selected"
   CustomEvent on the grid element with {id, thumb, full, thumbImg} so page-specific mockup
   scripts (prints-mockup.js, apparel-mockup.js) can react without this file knowing about them.
   thumbImg is the clicked button's own <img> element, already on screen — mockup scripts read
   its dimensions for aspect-ratio math instead of fetching the full-resolution image a second
   time just to probe its size. */

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
          thumbImg: button.querySelector("img"),
        },
      })
    );
  });

  // Select the first photo by default so the mockup preview isn't blank on load. Deferred to
  // a timeout so page-specific mockup scripts (loaded in a later <script> tag) have already
  // attached their "photo-selected" listener by the time this fires.
  const first = grid.querySelector(".catalogue-thumb");
  if (first) setTimeout(() => first.click(), 0);
});
