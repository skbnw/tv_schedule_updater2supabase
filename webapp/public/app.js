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

const DOW = ["日", "月", "火", "水", "木", "金", "土"];
let currentTab = "programs";
let politicianCache = [];

function escapeHtml(s) {
  return String(s || "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[c]));
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

function renderPrograms(rows) {
  resultsEl.innerHTML = "";
  for (const r of rows) {
    const li = document.createElement("li");
    li.className = "result";
    const archive = r.source === "archive" ? '<span class="badge">アーカイブ</span>' : "";
    li.innerHTML = `
      <div class="meta">${escapeHtml(fmtWhen(r.start_time, r.broadcast_date))} ・ ${escapeHtml(r.channel || "")} ${archive}</div>
      <h3>${escapeHtml(r.program_title || "(無題)")}</h3>
      <div class="snippet">${escapeHtml(r.snippet || r.description || "")}</div>
      <div class="detail">
        <div><strong>ジャンル</strong> ${escapeHtml(r.genre || "—")}</div>
        <p>${escapeHtml((r.description_detail || r.description || "（番組内容の登録なし）").trim())}</p>
        ${r.official_website ? `<p><a href="${escapeHtml(r.official_website)}" target="_blank" rel="noopener">公式サイト</a></p>` : ""}
      </div>
    `;
    li.addEventListener("click", () => li.classList.toggle("is-open"));
    resultsEl.appendChild(li);
  }
}

async function searchPrograms() {
  const params = programParams();
  csvLink.href = `/api/search?${params.toString()}&format=csv`;
  setStatus("検索中…");
  setTitle("");
  talentList.innerHTML = "";
  politicianList.innerHTML = "";
  const res = await fetch(`/api/search?${params.toString()}`);
  if (!res.ok) {
    setStatus("検索に失敗しました");
    resultsEl.innerHTML = "";
    return;
  }
  const { results } = await res.json();
  setStatus(`${results.length} 件`);
  renderPrograms(results);
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
    li.addEventListener("click", () => onPick(r));
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
  const res = await fetch(`/api/talents?${params.toString()}`);
  if (!res.ok) {
    setStatus("出演者の取得に失敗しました");
    return;
  }
  const { results } = await res.json();
  setStatus(`${results.length} 人`);
  setTitle("");
  renderPeople(talentList, results, loadAppearances);
}

async function loadAppearances(person) {
  setStatus("出演番組を取得中…");
  setTitle(`${person.name} の出演番組`);
  const res = await fetch(`/api/talents/${encodeURIComponent(person.talent_id)}/appearances`);
  if (!res.ok) {
    setStatus("出演番組の取得に失敗しました");
    return;
  }
  const { results } = await res.json();
  setStatus(`${results.length} 件`);
  renderPrograms(results);
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
  renderPeople(politicianList, results, loadPoliticianPrograms);
}

async function loadPoliticianPrograms(person) {
  const appearanceOnly = document.getElementById("appearanceOnly").checked;
  const params = new URLSearchParams();
  if (appearanceOnly) params.set("appearance_only", "1");
  setStatus("登場番組を取得中…");
  setTitle(`${person.name} の登場番組`);
  const res = await fetch(
    `/api/politicians/${encodeURIComponent(person.name)}/programs?${params.toString()}`
  );
  if (!res.ok) {
    setStatus("登場番組の取得に失敗しました");
    return;
  }
  const { results } = await res.json();
  setStatus(`${results.length} 件`);
  renderPrograms(results);
}

function switchTab(name) {
  currentTab = name;
  tabs.forEach((tab) => tab.classList.toggle("is-active", tab.dataset.tab === name));
  Object.entries(panels).forEach(([key, el]) => {
    el.classList.toggle("is-hidden", key !== name);
  });
  resultsEl.innerHTML = "";
  setTitle("");
  if (name === "programs") searchPrograms();
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
    document.getElementById("q").value = btn.dataset.q;
    searchPrograms();
  });
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
  searchPrograms();
}

boot();
