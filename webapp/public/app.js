const tabs = document.querySelectorAll(".tab");
const panels = {
  programs: document.getElementById("panel-programs"),
  talents: document.getElementById("panel-talents"),
  politicians: document.getElementById("panel-politicians"),
};
const statusEl = document.getElementById("status");
const resultsEl = document.getElementById("results");
const resultTitle = document.getElementById("resultTitle");
const csvLink = document.getElementById("csvLink");
const channelSelect = document.getElementById("channel");
const talentTag = document.getElementById("talentTag");
const talentList = document.getElementById("talentList");
const politicianList = document.getElementById("politicianList");
const profileCard = document.getElementById("profileCard");

const loadMoreWrap = document.getElementById("loadMoreWrap");
const loadMoreBtn = document.getElementById("loadMoreBtn");

const DOW = ["日", "月", "火", "水", "木", "金", "土"];
const PAGE_SIZE = 10;
let currentTab = "programs";
let politicianCache = [];
let pagedRows = [];
let pagedShown = 0;
let loadObserver = null;
let autoLoadReady = false;

function escapeHtml(s) {
  return String(s || "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[c]));
}

function todayJst() {
  const now = new Date();
  const jst = new Date(now.getTime() + 9 * 60 * 60 * 1000);
  return jst.toISOString().slice(0, 10);
}

function addDaysIso(iso, n) {
  const [y, m, d] = String(iso).split("-").map(Number);
  if (!y || !m || !d) return iso;
  return new Date(Date.UTC(y, m - 1, d + n)).toISOString().slice(0, 10);
}

function fillDefaultDates() {
  const fromEl = document.getElementById("from");
  const toEl = document.getElementById("to");
  if (!fromEl.value) fromEl.value = todayJst();
  if (!toEl.value) toEl.value = addDaysIso(todayJst(), 7);
}

function fmtWhen(startTime, broadcastDate) {
  const raw = String(startTime || "");
  if (raw.length >= 12) {
    const y = raw.slice(0, 4);
    const m = raw.slice(4, 6);
    const d = raw.slice(6, 8);
    const hh = raw.slice(8, 10);
    const mm = raw.slice(10, 12);
    const dt = new Date(`${y}-${m}-${d}T00:00:00`);
    const dow = Number.isNaN(dt.getTime()) ? "" : `（${DOW[dt.getDay()]}）`;
    return `${y}-${m}-${d}${dow} ${hh}:${mm}`;
  }
  return broadcastDate || "";
}

function setStatus(text) {
  statusEl.textContent = text || "";
}

function hideProfile() {
  profileCard.classList.add("is-hidden");
  profileCard.innerHTML = "";
}

function showProfile(p) {
  const rows = [
    ["読み", p.reading],
    ["議院", p.chamber],
    ["会派", p.party],
    ["選挙区", p.district],
    ["出身", p.birthplace],
    ["生年月日", p.birth_date],
    ["ジャンル", Array.isArray(p.genres) ? p.genres.join("、") : p.genres],
  ].filter(([, v]) => String(v || "").trim());
  const facts = rows
    .map(([k, v]) => `<div><dt>${escapeHtml(k)}</dt><dd>${escapeHtml(v)}</dd></div>`)
    .join("");
  const hits = p.tv_hits != null ? `テレビ登場 ${escapeHtml(p.tv_hits)}件` : "";
  const apps = p.appearances != null ? `出演 ${escapeHtml(p.appearances)}件` : "";
  const bio = compactText(p.career_history || p.wiki_extract || p.bio || "");
  const wiki = p.wiki_url
    ? `<p class="wiki"><a href="${escapeHtml(p.wiki_url)}" target="_blank" rel="noopener">Wikipediaで略歴を見る</a></p>`
    : (p.name
      ? `<p class="wiki"><a href="https://ja.wikipedia.org/wiki/${encodeURIComponent(p.name)}" target="_blank" rel="noopener">Wikipediaで略歴を見る</a></p>`
      : "");
  profileCard.innerHTML = `
    <h3>${escapeHtml(p.name || "")}</h3>
    ${facts ? `<dl class="facts">${facts}</dl>` : ""}
    ${hits || apps ? `<div class="hits">${hits || apps}</div>` : ""}
    <div class="bio">
      <h4>略歴</h4>
      ${bio ? `<p>${escapeHtml(bio)}</p>` : "<p class=\"empty\">登録された略歴はありません。</p>"}
      ${wiki}
    </div>
  `;
  profileCard.classList.toggle("is-hidden", !p.name);
}

function collapsePeople(target) {
  talentList.classList.remove("is-collapsed");
  politicianList.classList.remove("is-collapsed");
  if (target) target.classList.add("is-collapsed");
}

function setTitle(text) {
  if (!text) {
    resultTitle.classList.add("is-hidden");
    resultTitle.textContent = "";
    return;
  }
  resultTitle.classList.remove("is-hidden");
  resultTitle.textContent = text;
}

function programParams() {
  const params = new URLSearchParams();
  const q = document.getElementById("q").value.trim();
  const from = document.getElementById("from").value;
  const to = document.getElementById("to").value;
  const channel = document.getElementById("channel").value;
  if (q) params.set("q", q);
  if (from) params.set("from", from);
  if (to) params.set("to", to);
  if (channel) params.set("channel", channel);
  if (document.getElementById("upcoming").checked) params.set("upcoming", "1");
  if (document.getElementById("politicianOnly").checked) params.set("politician_only", "1");
  params.set("limit", "100");
  return params;
}

function compactText(s) {
  return String(s || "")
    .replace(/\u3000/g, " ")
    .replace(/[ \t]+/g, " ")
    .replace(/\n{2,}/g, "\n")
    .trim();
}

function programItem(r) {
  const li = document.createElement("li");
  li.className = "result";
  const archive = r.source === "archive" ? '<span class="badge">アーカイブ</span>' : "";
  const genre = r.genre ? `<span class="badge">${escapeHtml(r.genre)}</span>` : "";
  const body = compactText(r.description_detail || r.description || "");
  const site = r.official_website
    ? `<div class="links"><a href="${escapeHtml(r.official_website)}" target="_blank" rel="noopener">公式サイト</a></div>`
    : "";
  li.innerHTML = `
    <div class="meta">
      <span class="chev">▶</span>
      <span>${escapeHtml(fmtWhen(r.start_time, r.broadcast_date))}</span>
      <span>${escapeHtml(r.channel || "")}</span>
      ${genre}${archive}
    </div>
    <h3>${escapeHtml(r.program_title || "(無題)")}</h3>
    <div class="detail">
      <p>${escapeHtml(body || "（番組内容の登録なし）")}</p>
      ${site}
    </div>
  `;
  return li;
}

function updateLoadMore() {
  const remaining = pagedRows.length - pagedShown;
  if (remaining <= 0) {
    loadMoreWrap.classList.add("is-hidden");
    return;
  }
  loadMoreWrap.classList.remove("is-hidden");
  loadMoreBtn.textContent = `さらに${Math.min(PAGE_SIZE, remaining)}件`;
}

function appendPage() {
  if (pagedShown >= pagedRows.length) {
    updateLoadMore();
    return;
  }
  const next = pagedRows.slice(pagedShown, pagedShown + PAGE_SIZE);
  for (const row of next) resultsEl.appendChild(programItem(row));
  pagedShown += next.length;
  setStatus(`${pagedShown} / ${pagedRows.length} 件`);
  updateLoadMore();
}

function startPagedList(rows) {
  pagedRows = rows;
  pagedShown = 0;
  autoLoadReady = false;
  resultsEl.innerHTML = "";
  appendPage();
  if (loadObserver) loadObserver.disconnect();
  if (pagedShown < pagedRows.length) {
    const unlock = () => { autoLoadReady = true; };
    window.addEventListener("scroll", unlock, { once: true, passive: true });
    loadObserver = new IntersectionObserver((entries) => {
      if (!autoLoadReady) return;
      if (entries.some((e) => e.isIntersecting)) appendPage();
    }, { rootMargin: "80px" });
    loadObserver.observe(loadMoreWrap);
  }
}

function stopPagedList() {
  pagedRows = [];
  pagedShown = 0;
  loadMoreWrap.classList.add("is-hidden");
  if (loadObserver) {
    loadObserver.disconnect();
    loadObserver = null;
  }
}

function renderPrograms(rows) {
  stopPagedList();
  resultsEl.innerHTML = "";
  for (const r of rows) resultsEl.appendChild(programItem(r));
}

function sortNewest(rows) {
  return [...rows].sort((a, b) => {
    const ka = String(a.start_time || a.broadcast_date || "");
    const kb = String(b.start_time || b.broadcast_date || "");
    return kb.localeCompare(ka);
  });
}

async function searchPrograms() {
  const params = programParams();
  csvLink.href = `/api/search?${params.toString()}&format=csv`;
  setStatus("検索中…");
  setTitle("");
  hideProfile();
  talentList.innerHTML = "";
  politicianList.innerHTML = "";
  stopPagedList();
  const res = await fetch(`/api/search?${params.toString()}`);
  if (!res.ok) {
    setStatus("検索に失敗しました");
    resultsEl.innerHTML = "";
    return;
  }
  const { results } = await res.json();
  if (!results.length) {
    setStatus("該当する番組はありません");
    resultsEl.innerHTML = "";
    return;
  }
  setTitle(document.getElementById("q").value.trim() ? "検索結果" : "今日からの番組");
  startPagedList(results);
}

function renderPeople(target, rows, onPick) {
  target.innerHTML = "";
  for (const r of rows) {
    const li = document.createElement("li");
    li.className = "person";
    const meta = r.appearances != null
      ? `${r.appearances}件 / 最新 ${r.latest_date || "—"}`
      : `${r.tv_hits || 0}件 / ${r.party || ""} ${r.chamber || ""}`;
    li.innerHTML = `<span><strong>${escapeHtml(r.name)}</strong></span><span class="meta">${escapeHtml(meta)}</span>`;
    li.addEventListener("click", () => {
      target.querySelectorAll(".person").forEach((el) => el.classList.remove("is-selected"));
      li.classList.add("is-selected");
      collapsePeople(target);
      onPick(r);
    });
    target.appendChild(li);
  }
}

async function searchTalents() {
  const q = document.getElementById("talentQ").value.trim();
  const tag = document.getElementById("talentTag").value;
  if (!q && !tag) {
    setStatus("名前を入れるか、カテゴリを選んでください");
    return;
  }
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (tag) params.set("tag", tag);
  setStatus("検索中…");
  resultsEl.innerHTML = "";
  politicianList.innerHTML = "";
  stopPagedList();
  const res = await fetch(`/api/talents?${params.toString()}`);
  if (!res.ok) {
    setStatus("出演者の取得に失敗しました");
    return;
  }
  const { results } = await res.json();
  setStatus(`${results.length} 人`);
  setTitle("");
  hideProfile();
  talentList.classList.remove("is-collapsed");
  renderPeople(talentList, results, loadAppearances);
}

async function loadAppearances(person) {
  setStatus("出演番組を取得中…");
  setTitle(`${person.name} の出演番組`);
  stopPagedList();
  resultsEl.innerHTML = "";
  showProfile(person);
  fetch(`/api/profile?name=${encodeURIComponent(person.name)}&talent_id=${encodeURIComponent(person.talent_id || "")}`)
    .then((res) => (res.ok ? res.json() : null))
    .then((extra) => {
      if (extra && extra.profile) showProfile({ ...person, ...extra.profile });
    })
    .catch(() => {});
  const res = await fetch(`/api/talents/${encodeURIComponent(person.talent_id)}/appearances`);
  if (!res.ok) {
    setStatus("出演番組の取得に失敗しました");
    return;
  }
  const { results } = await res.json();
  if (!results.length) {
    setStatus("出演番組はありません");
    return;
  }
  startPagedList(sortNewest(results));
  resultTitle.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function loadPoliticians() {
  const q = document.getElementById("politicianQ").value.trim();
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  setStatus("名簿を取得中…");
  resultsEl.innerHTML = "";
  talentList.innerHTML = "";
  const res = await fetch(`/api/politicians?${params.toString()}`);
  if (!res.ok) {
    setStatus("議員名簿の取得に失敗しました");
    return;
  }
  const { results } = await res.json();
  politicianCache = results;
  setStatus(`${results.length} 人（テレビ登場のある議員）`);
  setTitle("");
  hideProfile();
  politicianList.classList.remove("is-collapsed");
  renderPeople(politicianList, results, loadPoliticianPrograms);
}

async function loadPoliticianPrograms(person) {
  const appearanceOnly = document.getElementById("appearanceOnly").checked;
  const params = new URLSearchParams();
  if (appearanceOnly) params.set("appearance_only", "1");
  setStatus("登場番組を取得中…");
  setTitle(`${person.name} の登場番組`);
  stopPagedList();
  resultsEl.innerHTML = "";
  showProfile(person);
  fetch(`/api/profile?name=${encodeURIComponent(person.name)}`)
    .then((res) => (res.ok ? res.json() : null))
    .then((extra) => {
      if (extra && extra.profile) showProfile({ ...person, ...extra.profile });
    })
    .catch(() => {});
  const res = await fetch(
    `/api/politicians/${encodeURIComponent(person.name)}/programs?${params.toString()}`
  );
  if (!res.ok) {
    setStatus("登場番組の取得に失敗しました");
    return;
  }
  const { results } = await res.json();
  if (!results.length) {
    setStatus("登場番組はありません");
    return;
  }
  startPagedList(sortNewest(results));
  resultTitle.scrollIntoView({ behavior: "smooth", block: "start" });
}

function switchTab(name) {
  currentTab = name;
  tabs.forEach((tab) => tab.classList.toggle("is-active", tab.dataset.tab === name));
  Object.entries(panels).forEach(([key, el]) => {
    el.classList.toggle("is-hidden", key !== name);
  });
  resultsEl.innerHTML = "";
  setTitle("");
  hideProfile();
  stopPagedList();
  if (name === "programs") {
    fillDefaultDates();
    searchPrograms();
  }
  if (name === "politicians" && politicianCache.length === 0) loadPoliticians();
}

tabs.forEach((tab) => {
  tab.addEventListener("click", () => switchTab(tab.dataset.tab));
});

document.getElementById("programForm").addEventListener("submit", (e) => {
  e.preventDefault();
  searchPrograms();
});
document.getElementById("talentForm").addEventListener("submit", (e) => {
  e.preventDefault();
  searchTalents();
});
document.getElementById("politicianForm").addEventListener("submit", (e) => {
  e.preventDefault();
  loadPoliticians();
});
document.querySelectorAll(".chip").forEach((btn) => {
  btn.addEventListener("click", () => {
    fillDefaultDates();
    document.getElementById("q").value = btn.dataset.q;
    searchPrograms();
  });
});
loadMoreBtn.addEventListener("click", appendPage);
resultsEl.addEventListener("click", (e) => {
  if (e.target.closest("a")) return;
  const item = e.target.closest("li.result");
  if (item) item.classList.toggle("is-open");
});

async function boot() {
  const [chRes, catRes] = await Promise.all([
    fetch("/api/channels"),
    fetch("/api/categories"),
  ]);
  if (chRes.ok) {
    const { channels } = await chRes.json();
    for (const c of channels) {
      const opt = document.createElement("option");
      opt.value = c.code;
      opt.textContent = c.name;
      channelSelect.appendChild(opt);
    }
  }
  if (catRes.ok) {
    const { results } = await catRes.json();
    for (const row of results) {
      const opt = document.createElement("option");
      opt.value = row.tag_name;
      opt.textContent = `${row.description}（${row.n}）`;
      talentTag.appendChild(opt);
    }
  }
  csvLink.href = "/api/search?format=csv&limit=100";
  fillDefaultDates();
  searchPrograms();
}

boot();
