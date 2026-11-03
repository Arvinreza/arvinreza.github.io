"use strict";
/* The single source of truth is data/publications_manual.csv.
 * No ORCID requests or background updates occur in the browser. */
(() => {
  const list = document.getElementById("publication-list");
  const counter = document.getElementById("publication-count");
  const search = document.getElementById("publication-search");
  const clear = document.getElementById("clear-search");
  let publications = [];

  function parseCSV(input) {
    const text = input.replace(/^\uFEFF/, "");
    const rows = [];
    let fields = [], field = "", inQuotes = false;
    for (let i = 0; i < text.length; i++) {
      const ch = text[i];
      if (inQuotes) {
        if (ch === '"' && text[i + 1] === '"') { field += '"'; i++; }
        else if (ch === '"') inQuotes = false;
        else field += ch;
      } else if (ch === '"') {
        inQuotes = true;
      } else if (ch === ",") {
        fields.push(field);
        field = "";
      } else if (ch === "\n") {
        fields.push(field.replace(/\r$/, ""));
        rows.push(fields);
        fields = [];
        field = "";
      } else {
        field += ch;
      }
    }
    if (inQuotes) throw new Error("Unterminated quoted field");
    if (fields.length || field) { fields.push(field); rows.push(fields); }
    const headers = rows.shift();
    if (!headers || !headers.includes("title") || !headers.includes("year")) {
      throw new Error("Invalid publication CSV headers");
    }
    return rows.filter(row => row.some(Boolean)).map(row => {
      if (row.length !== headers.length) throw new Error("Invalid publication CSV row");
      return Object.fromEntries(headers.map((key, index) => [key, row[index]]));
    });
  }

  function safeURL(value) {
    if (!value) return null;
    try {
      const url = new URL(value);
      return url.protocol === "https:" || url.protocol === "http:" ? url.href : null;
    } catch { return null; }
  }

  function makeText(tag, className, value) {
    const el = document.createElement(tag);
    if (className) el.className = className;
    el.textContent = value || "";
    return el;
  }

  function externalLink(parent, label, href, className) {
    const uri = safeURL(href);
    if (!uri) return false;
    const a = makeText("a", className, label);
    a.href = uri;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    parent.append(a);
    return true;
  }

  function createPublication(p) {
    const article = document.createElement("article");
    article.className = "publication";

    const authors = p.authors.replace(/;\s*/g, "; ");
    article.append(makeText("p", "pub-authors", authors + " (" + p.year + ")"));

    const h = makeText("h4", "pub-title", "");
    if (!externalLink(h, p.title, p.publication_url || (p.doi && "https://doi.org/" + p.doi))) {
      h.textContent = p.title;
    }
    article.append(h);

    if (p.publication_details) article.append(makeText("p", "pub-details", p.publication_details));

    const links = makeText("div", "pub-links", "");
    if (p.doi) externalLink(links, "DOI ↗", "https://doi.org/" + p.doi);
    else if (p.publication_url) externalLink(links, "Publication ↗", p.publication_url);
    if (p.preprint_url) externalLink(links, "Preprint ↗", p.preprint_url);
    if (p.data_url) externalLink(links, "Data ↗", p.data_url);
    if (p.full_text_url && p.full_text_url !== p.publication_url) externalLink(links, "Full text ↗", p.full_text_url);
    if (p.related_url) externalLink(links, p.related_label ? p.related_label + " ↗" : "Related version ↗", p.related_url);
    if (links.childElementCount) article.append(links);
    return article;
  }

  function render() {
    const query = search.value.trim().toLocaleLowerCase();
    const found = publications.filter(p => !query ||
      [p.title, p.authors, p.publication_details, p.doi, p.year].join(" ").toLocaleLowerCase().includes(query));
    counter.textContent = query ? found.length + " of " + publications.length + " works" : publications.length + " works";
    clear.hidden = !query;
    list.replaceChildren();
    if (!found.length) {
      list.append(makeText("p", "empty-state", query ? "No publications match your search." : "No publications are currently listed."));
      list.setAttribute("aria-busy", "false");
      return;
    }
    let currentYear = null;
    let currentContainer = null;
    for (const p of found) {
      if (p.year !== currentYear) {
        const section = document.createElement("section");
        section.className = "year-group";
        const title = makeText("h3", null, p.year);
        section.setAttribute("aria-label", "Publications from " + p.year);
        section.append(title);
        currentContainer = document.createElement("div");
        currentContainer.className = "year-publications";
        section.append(currentContainer);
        list.append(section);
        currentYear = p.year;
      }
      currentContainer.append(createPublication(p));
    }
    list.setAttribute("aria-busy", "false");
  }

  async function initialize() {
    try {
      const response = await fetch("data/publications_manual.csv", { cache: "no-cache" });
      if (!response.ok) throw new Error("Could not fetch publication CSV: " + response.status);
      publications = parseCSV(await response.text());
      publications.sort((a, b) => Number(b.year) - Number(a.year));
      render();
    } catch (error) {
      console.warn(error);
      list.replaceChildren();
      list.append(makeText("p", "empty-state", "Publication list temporarily unavailable. Please consult the linked IDS bibliography."));
      list.setAttribute("aria-busy", "false");
    }
  }

  search.addEventListener("input", render);
  clear.addEventListener("click", () => {
    search.value = "";
    render();
    search.focus();
  });
  initialize();
})();
