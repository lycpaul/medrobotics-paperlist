"use strict";

const form = document.getElementById("search-form");
const qInput = document.getElementById("q");
const keywordInput = document.getElementById("keyword");
const conferenceSelect = document.getElementById("conference");
const yearSelect = document.getElementById("year");
const statusEl = document.getElementById("status");
const tbody = document.getElementById("results-body");
const pager = document.getElementById("pager");
const prevBtn = document.getElementById("prev");
const nextBtn = document.getElementById("next");
const pageInfo = document.getElementById("page-info");
const themeToggle = document.getElementById("theme-toggle");
const exportBtn = document.getElementById("export");
const pageSizeSelect = document.getElementById("page-size");

// --- Theme (light/dark) ---------------------------------------------------
const THEME_KEY = "paperlist-theme";

function systemTheme() {
  return window.matchMedia &&
    window.matchMedia("(prefers-color-scheme: light)").matches
    ? "light"
    : "dark";
}

function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  themeToggle.textContent = theme === "light" ? "🌙 Dark" : "☀ Light";
}

function initTheme() {
  applyTheme(localStorage.getItem(THEME_KEY) || systemTheme());
}

themeToggle.addEventListener("click", () => {
  const next =
    document.documentElement.getAttribute("data-theme") === "light"
      ? "dark"
      : "light";
  localStorage.setItem(THEME_KEY, next);
  applyTheme(next);
});

initTheme();

const PAGE_SIZE_KEY = "paperlist-page-size";
let pageSize = 50;
let currentPage = 1;
let totalResults = 0;
// Filter params of the last search run, so Export matches what is shown even
// if the form has been edited since.
let lastFilters = "";

function selectedValues(select) {
  return Array.from(select.selectedOptions).map((o) => o.value);
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text == null ? "" : String(text);
  return div.innerHTML;
}

// Highlight occurrences of `term` in already-escaped text.
function highlight(escaped, term) {
  if (!term) return escaped;
  const safe = term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return escaped.replace(new RegExp(safe, "gi"), (m) => `<mark>${m}</mark>`);
}

function buildFilters() {
  const params = new URLSearchParams();
  if (qInput.value.trim()) params.set("q", qInput.value.trim());
  if (keywordInput.value.trim()) params.set("keyword", keywordInput.value.trim());
  selectedValues(conferenceSelect).forEach((c) => params.append("conference", c));
  selectedValues(yearSelect).forEach((y) => params.append("year", y));
  return params;
}

function buildQuery(page) {
  const params = buildFilters();
  params.set("page", page);
  params.set("page_size", pageSize);
  return params.toString();
}

function linkCell(links) {
  if (!links) return '<span class="empty">—</span>';
  const labels = { pdf: "PDF", code: "Code", dataset: "Data", paper_page: "Page" };
  const parts = [];
  for (const key of ["pdf", "code", "dataset", "paper_page"]) {
    const url = links[key];
    if (url) {
      parts.push(
        `<a href="${escapeHtml(url)}" target="_blank" rel="noopener">${labels[key]}</a>`
      );
    }
  }
  return parts.length ? parts.join("") : '<span class="empty">—</span>';
}

function renderRows(results, term) {
  tbody.innerHTML = "";
  if (!results.length) {
    const tr = document.createElement("tr");
    tr.innerHTML = '<td colspan="5" class="empty">No papers match your query.</td>';
    tbody.appendChild(tr);
    return;
  }
  for (const paper of results) {
    const row = document.createElement("tr");
    row.className = "paper-row";
    const topic = paper.session || paper.keywords || "";
    row.innerHTML =
      `<td class="title-cell">${highlight(escapeHtml(paper.title), term)}</td>` +
      `<td class="authors-cell">${escapeHtml(paper.authors)}</td>` +
      `<td><span class="venue-badge">${escapeHtml(paper.conference)} ${paper.year}</span></td>` +
      `<td class="topic-cell">${escapeHtml(topic)}</td>` +
      `<td class="links-cell">${linkCell(paper.links)}</td>`;

    const abstractRow = document.createElement("tr");
    abstractRow.className = "abstract-row";
    abstractRow.hidden = true;
    const abstract = paper.abstract
      ? highlight(escapeHtml(paper.abstract), term)
      : '<span class="empty">No abstract available.</span>';
    abstractRow.innerHTML =
      `<td colspan="5"><span class="abstract-label">Abstract</span>${abstract}</td>`;

    row.addEventListener("click", () => {
      abstractRow.hidden = !abstractRow.hidden;
    });

    tbody.appendChild(row);
    tbody.appendChild(abstractRow);
  }
}

function updatePager() {
  const totalPages = Math.max(1, Math.ceil(totalResults / pageSize));
  pager.hidden = totalResults === 0;
  pageInfo.textContent = `Page ${currentPage} of ${totalPages}`;
  prevBtn.disabled = currentPage <= 1;
  nextBtn.disabled = currentPage >= totalPages;
}

async function runSearch(page) {
  currentPage = page;
  statusEl.textContent = "Searching…";
  exportBtn.disabled = true;
  try {
    const resp = await fetch(`/api/search?${buildQuery(page)}`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    totalResults = data.total;
    lastFilters = buildFilters().toString();
    exportBtn.disabled = data.total === 0;
    renderRows(data.results, qInput.value.trim());
    const shownFrom = data.total ? (page - 1) * pageSize + 1 : 0;
    const shownTo = Math.min(page * pageSize, data.total);
    statusEl.textContent = data.total
      ? `${data.total.toLocaleString()} result(s) — showing ${shownFrom}–${shownTo}`
      : "0 results";
    updatePager();
  } catch (err) {
    statusEl.textContent = `Error: ${err.message}`;
  }
}

async function loadFacets() {
  try {
    const resp = await fetch("/api/facets");
    const data = await resp.json();
    for (const c of data.conferences) {
      conferenceSelect.add(new Option(c, c));
    }
    for (const y of data.years) {
      yearSelect.add(new Option(y, y));
    }
  } catch (err) {
    statusEl.textContent = `Could not load filters: ${err.message}`;
  }
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  runSearch(1);
});

document.getElementById("reset").addEventListener("click", () => {
  form.reset();
  runSearch(1);
});

exportBtn.addEventListener("click", () => {
  // The server responds with Content-Disposition: attachment, so this downloads
  // the file without navigating away.
  window.location.href = `/api/export?${lastFilters}`;
});

function initPageSize() {
  const saved = localStorage.getItem(PAGE_SIZE_KEY);
  if (saved && Array.from(pageSizeSelect.options).some((o) => o.value === saved)) {
    pageSizeSelect.value = saved;
  }
  pageSize = Number(pageSizeSelect.value);
}

pageSizeSelect.addEventListener("change", () => {
  pageSize = Number(pageSizeSelect.value);
  localStorage.setItem(PAGE_SIZE_KEY, pageSizeSelect.value);
  runSearch(1);
});

initPageSize();

prevBtn.addEventListener("click", () => {
  if (currentPage > 1) runSearch(currentPage - 1);
});
nextBtn.addEventListener("click", () => {
  runSearch(currentPage + 1);
});

(async function init() {
  await loadFacets();
  runSearch(1);
})();
