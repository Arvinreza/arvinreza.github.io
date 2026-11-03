'use strict';
(() => {
  const list = document.querySelector('#publication-list');
  const search = document.querySelector('#publication-search');
  const yearSelect = document.querySelector('#year-filter');
  const typeSelect = document.querySelector('#type-filter');
  const reset = document.querySelector('#reset-filters');
  const resultCount = document.querySelector('#result-count');
  let publications = [];

  function safeUrl(value) {
    try {
      const url = new URL(value);
      return ['https:', 'http:'].includes(url.protocol) ? url.href : null;
    } catch { return null; }
  }
  function textElement(tag, className, value) {
    const el = document.createElement(tag);
    if (className) el.className = className;
    el.textContent = String(value || '');
    return el;
  }
  function addLink(container, label, url) {
    const safe = safeUrl(url);
    if (!safe) return;
    const link = textElement('a', null, label);
    link.href = safe;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    container.append(link);
  }
  function displayAuthors(authors) {
    if (typeof authors === 'string') return authors;
    if (Array.isArray(authors)) return authors.join(', ');
    return '';
  }
  function createCard(item) {
    const article = document.createElement('article');
    article.className = 'publication-card';
    article.append(textElement('p', 'pub-type', item.type_label || 'Research output'));
    const h3 = textElement('h3', 'pub-title', '');
    const doiUrl = item.doi ? `https://doi.org/${encodeURIComponent(item.doi).replace(/%2F/gi, '/')}` : null;
    const primary = safeUrl(doiUrl) || safeUrl(item.url);
    if (primary) addLink(h3, item.title, primary);
    else h3.textContent = item.title || 'Untitled work';
    article.append(h3);
    const authors = displayAuthors(item.authors);
    if (authors) article.append(textElement('p', 'pub-authors', authors));
    const details = [item.venue, item.volume ? `Vol. ${item.volume}` : null, item.issue ? `No. ${item.issue}` : null, item.pages].filter(Boolean);
    if (details.length) article.append(textElement('p', 'pub-meta', details.join(' · ')));
    const links = document.createElement('div');
    links.className = 'pub-links';
    if (doiUrl) addLink(links, 'DOI ↗', doiUrl);
    if (safeUrl(item.url) && item.url !== doiUrl) addLink(links, 'Publication ↗', item.url);
    if (links.childElementCount) article.append(links);
    return article;
  }
  function render() {
    const query = search.value.trim().toLocaleLowerCase();
    const year = yearSelect.value;
    const type = typeSelect.value;
    const filtered = publications.filter(p => {
      const matchesYear = year === 'all' || String(p.year || 'Undated') === year;
      const matchesType = type === 'all' || p.type_label === type;
      const searchable = [p.title, p.venue, p.doi, p.type_label, displayAuthors(p.authors)].join(' ').toLocaleLowerCase();
      return matchesYear && matchesType && (!query || searchable.includes(query));
    });
    list.replaceChildren();
    list.setAttribute('aria-busy', 'false');
    resultCount.textContent = `${filtered.length} of ${publications.length} publications`;
    reset.hidden = !query && year === 'all' && type === 'all';
    if (!publications.length) {
      const message = textElement('p', 'empty-state', 'No works have been imported yet. The first publication sync will run when GitHub Pages is deployed. ');
      addLink(message, 'View the public ORCID record ↗', 'https://orcid.org/0000-0002-9630-9680');
      list.append(message);
      return;
    }
    if (!filtered.length) { list.append(textElement('p', 'empty-state', 'No publications match these filters. Try a different search.')); return; }
    let lastYear = null;
    let container = null;
    for (const item of filtered) {
      const currentYear = String(item.year || 'Undated');
      if (currentYear !== lastYear) {
        const section = document.createElement('section');
        section.className = 'publication-year';
        section.append(textElement('h3', 'year-heading', currentYear));
        container = document.createElement('div');
        container.className = 'year-items';
        section.append(container);
        list.append(section);
        lastYear = currentYear;
      }
      container.append(createCard(item));
    }
  }
  function fillOptions(select, values) {
    values.forEach(value => {
      const option = document.createElement('option');
      option.value = String(value);
      option.textContent = String(value);
      select.append(option);
    });
  }
  async function init() {
    try {
      const response = await fetch('data/publications.json', { cache: 'no-cache' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (!Array.isArray(data.publications)) throw new Error('Invalid publication data');
      publications = data.publications.slice().sort((a, b) => (Number(b.year)||0)-(Number(a.year)||0) || (a.title||'').localeCompare(b.title||''));
      document.querySelector('#publication-count').textContent = String(publications.length);
      document.querySelector('#latest-year').textContent = String(publications.find(p => p.year)?.year || '—');
      if (data.generated_at) {
        const date = new Date(data.generated_at);
        if (!isNaN(date.valueOf())) document.querySelector('#updated-at').textContent = `Last sync: ${new Intl.DateTimeFormat('en', {year:'numeric', month:'short', day:'numeric', timeZone:'UTC'}).format(date)} (UTC)`;
      }
      fillOptions(yearSelect, [...new Set(publications.map(p => String(p.year || 'Undated')))]);
      fillOptions(typeSelect, [...new Set(publications.map(p => p.type_label || 'Research output'))].sort());
      render();
    } catch (err) {
      list.replaceChildren();
      list.setAttribute('aria-busy', 'false');
      list.append(textElement('p', 'empty-state', 'Publication data is temporarily unavailable. Please use the ORCID link above.'));
      console.warn('Could not load publication data:', err);
    }
  }
  search.addEventListener('input', render);
  yearSelect.addEventListener('change', render);
  typeSelect.addEventListener('change', render);
  reset.addEventListener('click', () => { search.value = ''; yearSelect.value = 'all'; typeSelect.value = 'all'; render(); search.focus(); });
  init();
})();
