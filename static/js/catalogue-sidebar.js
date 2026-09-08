/* Category sidebar + jump links for the catalogue grid (issue #74): clicking a category button
   scrolls the grid to that category's heading; an IntersectionObserver highlights whichever
   category is currently in view as the client scrolls the grid manually. Purely navigational —
   selecting a photo is still catalogue-picker.js's job, untouched here. */

document.querySelectorAll(".cat-sidebar").forEach((nav) => {
  const grid = nav.parentElement.querySelector(".catalogue-grid");
  if (!grid) return;

  const buttons = Array.from(nav.querySelectorAll("button[data-target]"));
  const sections = buttons
    .map((button) => document.getElementById(button.dataset.target))
    .filter(Boolean);

  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const setActive = (button) => {
    buttons.forEach((b) => b.classList.toggle("is-active", b === button));
  };

  // A click-triggered scroll animates — for the ~8000px the full catalogue grid can run to,
  // smooth scrolling takes over a second — and a category near the very end can't always reach
  // the true top (nothing left below it to scroll past). Either way, several short sections can
  // end up inside the observer's "current" band at once, mid-animation or once it settles at a
  // clamped position. Suppressing the observer until the scroll actually finishes (not just a
  // guessed delay) stops it re-highlighting a different section than the one actually clicked.
  let suppressed = false;
  const supportsScrollEnd = "onscrollend" in window;

  nav.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-target]");
    if (!button) return;
    const target = document.getElementById(button.dataset.target);
    if (!target) return;
    setActive(button);
    suppressed = true;
    const resume = () => { suppressed = false; };
    if (supportsScrollEnd) {
      grid.addEventListener("scrollend", resume, { once: true });
    } else {
      // Safari (pre-17.4) has no scrollend event — fall back to a generous fixed delay rather
      // than leaving the observer suppressed indefinitely.
      setTimeout(resume, 2500);
    }
    target.scrollIntoView({ block: "start", behavior: reduceMotion ? "auto" : "smooth" });
  });

  // rootMargin trims the bottom 70% of the grid's viewport so a section is marked "current" as
  // soon as its heading crosses into the top portion, rather than only once it's fully in view
  // — matches how a reader actually tracks "which section am I in" while scrolling. When more
  // than one section sits inside that band at once, the topmost wins rather than whichever the
  // browser happens to report last (that order isn't spec-guaranteed to match reading order).
  const observer = new IntersectionObserver(
    (entries) => {
      if (suppressed) return;
      const visible = entries.filter((entry) => entry.isIntersecting);
      if (visible.length === 0) return;
      const topmost = visible.reduce((a, b) =>
        a.boundingClientRect.top <= b.boundingClientRect.top ? a : b
      );
      setActive(buttons[sections.indexOf(topmost.target)]);
    },
    { root: grid, rootMargin: "0px 0px -70% 0px", threshold: 0 }
  );
  sections.forEach((section) => observer.observe(section));
});
