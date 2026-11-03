"use strict";
/* Publication entries are embedded in index.html at build time.
   Search is progressively enhanced; entries remain visible without JavaScript. */
(() => {
  const input = document.getElementById("publication-search");
  const clear = document.getElementById("clear-search");
  const count = document.getElementById("publication-count");
  const groups = Array.from(document.querySelectorAll(".year-group"));
  if (!input || !clear || !count || !groups.length) return;
  const articles = Array.from(document.querySelectorAll(".publication"));
  const total = articles.length;
  const apply = () => {
    const query = input.value.trim().toLocaleLowerCase();
    let visible = 0;
    for (const article of articles) {
      const match = !query || article.textContent.toLocaleLowerCase().includes(query);
      article.hidden = !match;
      if (match) visible++;
    }
    for (const group of groups) {
      group.hidden = !Array.from(group.querySelectorAll(".publication")).some(item => !item.hidden);
    }
    count.textContent = query ? `${visible} of ${total} works` : `${total} works`;
    clear.hidden = !query;
  };
  input.addEventListener("input", apply);
  clear.addEventListener("click", () => {
    input.value = "";
    apply();
    input.focus();
  });
})();
