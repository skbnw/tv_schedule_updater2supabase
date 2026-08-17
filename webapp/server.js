// T-Clip 公開検索 API
// v1.0.0 (2026-08-17)
// 追加: p330 録画検索の公開版。番組キーワード / 出演者 / 議員を Supabase RPC 経由で検索
// v1.0.1 (2026-08-17)
// 追加: 議員の略歴（名簿＋talent_profiles）を /api/profile で返す
const path = require("path");
const fs = require("fs");
const express = require("express");
const { createClient } = require("@supabase/supabase-js");

const envPath = path.join(__dirname, ".env");
if (fs.existsSync(envPath)) {
  for (const line of fs.readFileSync(envPath, "utf8").split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const eq = trimmed.indexOf("=");
    if (eq < 1) continue;
    const key = trimmed.slice(0, eq).trim();
    const val = trimmed.slice(eq + 1).trim();
    if (key && process.env[key] == null) process.env[key] = val;
  }
}

const PORT = Number(process.env.PORT) || 8080;
const SUPABASE_URL = (process.env.SUPABASE_URL || "").trim();
const SUPABASE_KEY = (
  process.env.SUPABASE_SECRET_KEY ||
  process.env.SUPABASE_KEY ||
  ""
).trim();
const JSON_LIMIT_DEFAULT = 50;
const JSON_LIMIT_MAX = 300;
const CSV_ROW_CAP = 1000;

const CHANNELS = [
  { code: "NHKG-TKY", name: "NHK総合" },
  { code: "NHKE-TKY", name: "NHK Eテレ" },
  { code: "NTV-TKY", name: "日テレ" },
  { code: "TV-ASAHI-TKY", name: "テレビ朝日" },
  { code: "TBS-TKY", name: "TBS" },
  { code: "TV-TOKYO-TKY", name: "テレビ東京" },
  { code: "FUJI-TV-TKY", name: "フジテレビ" },
  { code: "NHK-BS", name: "NHK BS" },
  { code: "BS-NTV", name: "BS日テレ" },
  { code: "BS-ASAHI", name: "BS朝日" },
  { code: "BS-TBS", name: "BS-TBS" },
  { code: "BS-TV-TOKYO", name: "BSテレ東" },
  { code: "BS-FUJI", name: "BSフジ" },
  { code: "BS11", name: "BS11" },
];

if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error("SUPABASE_URL と SUPABASE_SECRET_KEY（または SUPABASE_KEY）が必要です。");
  process.exit(1);
}

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY, {
  auth: { persistSession: false, autoRefreshToken: false },
  realtime: { disabled: true },
});

function parseCsvLine(line) {
  return line.split(",").map((c) => c.trim());
}

function loadGazetteer() {
  const candidates = [
    path.join(__dirname, "data", "politicians_gazetteer.csv"),
    path.join(__dirname, "..", "reference", "politicians_gazetteer.csv"),
  ];
  const map = new Map();
  for (const file of candidates) {
    if (!fs.existsSync(file)) continue;
    const lines = fs.readFileSync(file, "utf8").split(/\r?\n/).filter(Boolean);
    const header = parseCsvLine(lines.shift() || "");
    const idx = Object.fromEntries(header.map((h, i) => [h, i]));
    for (const line of lines) {
      const cols = parseCsvLine(line);
      const name = cols[idx.name];
      if (!name) continue;
      map.set(name, {
        reading: cols[idx.reading] || "",
        party: cols[idx.party] || "",
        chamber: cols[idx.chamber] || "",
        district: cols[idx.district] || "",
      });
    }
    break;
  }
  return map;
}

const gazetteer = loadGazetteer();
app.disable("x-powered-by");
app.use(express.json());
app.use(express.static(path.join(__dirname, "public")));

function parseLimit(raw, fallback, max) {
  const n = Number.parseInt(String(raw ?? ""), 10);
  if (!Number.isFinite(n) || n <= 0) return fallback;
  return Math.min(n, max);
}

function todayJst() {
  const now = new Date();
  const jst = new Date(now.getTime() + 9 * 60 * 60 * 1000);
  return jst.toISOString().slice(0, 10);
}

function filterPrograms(rows, { channel, from, to, upcoming }) {
  const today = todayJst();
  return (rows || []).filter((r) => {
    if (channel && r.channel_code !== channel && r.channel !== channel) return false;
    const d = String(r.broadcast_date || "");
    if (from && d < from) return false;
    if (to && d > to) return false;
    if (upcoming && d && d < today) return false;
    return true;
  });
}

function snippetFrom(row, q) {
  const text = [row.description_detail, row.description, row.program_title]
    .filter(Boolean)
    .join(" ")
    .replace(/\s+/g, " ")
    .trim();
  if (!text) return "";
  if (!q) return text.slice(0, 90);
  const term = q.trim().split(/\s+/)[0];
  const idx = term ? text.indexOf(term) : -1;
  if (idx < 0) return text.slice(0, 90);
  const start = Math.max(0, idx - 24);
  return `${start > 0 ? "…" : ""}${text.slice(start, start + 100)}…`;
}

function publicProgram(row, q) {
  return {
    event_id: row.event_id,
    broadcast_date: row.broadcast_date,
    start_time: row.start_time,
    end_time: row.end_time,
    channel: row.channel,
    channel_code: row.channel_code,
    program_title: row.program_title,
    genre: row.genre,
    source: row.source,
    official_website: row.official_website || "",
    description: row.description || "",
    description_detail: row.description_detail || "",
    snippet: snippetFrom(row, q),
  };
}

async function rpc(name, params) {
  const { data, error } = await supabase.rpc(name, params);
  if (error) {
    const err = new Error(error.message || "rpc failed");
    err.status = 400;
    err.details = error;
    throw err;
  }
  return data || [];
}

async function searchPrograms({ q, channel, from, to, upcoming, politicianOnly, limit }) {
  let rows;
  if (q) {
    rows = await rpc("app_search", {
      p_query: q,
      p_politician_only: Boolean(politicianOnly),
      p_limit: limit,
    });
  } else {
    let query = supabase
      .from("v_program_search")
      .select(
        "event_id, broadcast_date, start_time, end_time, channel, channel_code, program_title, genre, source, official_website, description, description_detail"
      )
      .order("broadcast_date", { ascending: false })
      .limit(limit);
    if (from) query = query.gte("broadcast_date", from);
    if (to) query = query.lte("broadcast_date", to);
    if (channel) query = query.eq("channel_code", channel);
    const { data, error } = await query;
    if (error) {
      // ビュー未公開時は稼働テーブルへフォールバック
      let fallback = supabase
        .from("programs")
        .select(
          "event_id, broadcast_date, start_time, end_time, channel, channel_code, program_title, genre, official_website, description, description_detail"
        )
        .order("broadcast_date", { ascending: false })
        .limit(limit);
      if (from) fallback = fallback.gte("broadcast_date", from);
      if (to) fallback = fallback.lte("broadcast_date", to);
      if (channel) fallback = fallback.eq("channel_code", channel);
      const fb = await fallback;
      if (fb.error) throw new Error(fb.error.message);
      rows = (fb.data || []).map((r) => ({ ...r, source: "live" }));
    } else {
      rows = data || [];
    }
  }
  return filterPrograms(rows, { channel, from, to, upcoming }).map((r) =>
    publicProgram(r, q)
  );
}

function toCsv(rows) {
  const header = ["日付", "開始", "局名", "番組名", "ジャンル", "概要", "公式"];
  const escape = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
  const lines = [header.map(escape).join(",")];
  for (const r of rows) {
    lines.push(
      [
        r.broadcast_date || "",
        r.start_time || "",
        r.channel || "",
        r.program_title || "",
        r.genre || "",
        r.snippet || r.description || "",
        r.official_website || "",
      ]
        .map(escape)
        .join(",")
    );
  }
  return `\ufeff${lines.join("\r\n")}\r\n`;
}

function boolParam(v) {
  return v === "1" || v === "true" || v === "on";
}

app.get("/api/health", (_req, res) => {
  res.json({ ok: true, app: "tclip-search" });
});

app.get("/api/channels", (_req, res) => {
  res.json({ channels: CHANNELS });
});

app.get("/api/search", async (req, res) => {
  const q = String(req.query.q || "").trim();
  const channel = String(req.query.channel || "").trim();
  const from = String(req.query.from || "").trim();
  const to = String(req.query.to || "").trim();
  const upcoming = boolParam(req.query.upcoming);
  const politicianOnly = boolParam(req.query.politician_only);
  const format = String(req.query.format || "json");
  const limit = parseLimit(
    req.query.limit,
    format === "csv" ? CSV_ROW_CAP : JSON_LIMIT_DEFAULT,
    format === "csv" ? CSV_ROW_CAP : JSON_LIMIT_MAX
  );

  try {
    const results = await searchPrograms({
      q,
      channel,
      from,
      to,
      upcoming,
      politicianOnly,
      limit,
    });
    if (format === "csv") {
      res.setHeader("Content-Type", "text/csv; charset=utf-8");
      res.setHeader("Content-Disposition", 'attachment; filename="tclip-programs.csv"');
      res.send(toCsv(results));
      return;
    }
    res.json({ results, count: results.length });
  } catch (err) {
    console.error("search error:", err.message, err.details || "");
    res.status(err.status || 500).json({ error: "検索に失敗しました" });
  }
});

app.get("/api/talents", async (req, res) => {
  const q = String(req.query.q || "").trim();
  const tag = String(req.query.tag || "").trim();
  const limit = parseLimit(req.query.limit, 60, 100);
  try {
    let rows;
    if (q) {
      rows = await rpc("app_talent_search", { p_query: q, p_limit: limit });
    } else if (tag) {
      rows = await rpc("app_talents", { p_tag: tag });
    } else {
      res.status(400).json({ error: "q または tag を指定してください" });
      return;
    }
    res.json({ results: rows });
  } catch (err) {
    console.error("talents error:", err.message);
    res.status(err.status || 500).json({ error: "出演者の取得に失敗しました" });
  }
});

app.get("/api/categories", async (_req, res) => {
  try {
    const rows = await rpc("app_categories");
    res.json({ results: rows });
  } catch (err) {
    console.error("categories error:", err.message);
    res.status(err.status || 500).json({ error: "カテゴリの取得に失敗しました" });
  }
});

app.get("/api/talents/:id/appearances", async (req, res) => {
  try {
    const rows = await rpc("app_appearances", { p_talent_id: String(req.params.id) });
    const channel = String(req.query.channel || "").trim();
    const from = String(req.query.from || "").trim();
    const to = String(req.query.to || "").trim();
    const upcoming = boolParam(req.query.upcoming);
    const results = filterPrograms(rows, { channel, from, to, upcoming }).map((r) =>
      publicProgram(r, "")
    );
    res.json({ results, count: results.length });
  } catch (err) {
    console.error("appearances error:", err.message);
    res.status(err.status || 500).json({ error: "出演番組の取得に失敗しました" });
  }
});

app.get("/api/politicians", async (req, res) => {
  const q = String(req.query.q || "").trim();
  try {
    let rows = await rpc("app_politicians", { p_min_hits: 1 });
    if (q) {
      rows = rows.filter((r) => String(r.name || "").includes(q));
    }
    res.json({ results: rows });
  } catch (err) {
    console.error("politicians error:", err.message);
    res.status(err.status || 500).json({ error: "議員名簿の取得に失敗しました" });
  }
});

app.get("/api/politicians/:name/programs", async (req, res) => {
  const appearanceOnly = boolParam(req.query.appearance_only);
  const limit = parseLimit(req.query.limit, 300, 300);
  try {
    const rows = await rpc("app_politician_programs", {
      p_name: decodeURIComponent(req.params.name),
      p_limit: limit,
      p_appearance_only: appearanceOnly,
    });
    res.json({
      results: rows.map((r) => publicProgram(r, req.params.name)),
      count: rows.length,
    });
  } catch (err) {
    console.error("politician programs error:", err.message);
    res.status(err.status || 500).json({ error: "登場番組の取得に失敗しました" });
  }
});

app.get("/api/profile", async (req, res) => {
  const name = String(req.query.name || "").trim();
  const talentId = String(req.query.talent_id || "").trim();
  if (!name && !talentId) {
    res.status(400).json({ error: "name または talent_id が必要です" });
    return;
  }
  const profile = { name, ...(gazetteer.get(name) || {}) };
  try {
    let tid = talentId;
    if (!tid && name) {
      const talents = await supabase
        .from("talents")
        .select("talent_id, name, link")
        .eq("name", name)
        .limit(1);
      if (talents.data && talents.data[0]) tid = String(talents.data[0].talent_id);
    }
    if (tid) {
      const rows = await supabase
        .from("talent_profiles")
        .select("full_name, reading, birth_date, birthplace, career_history, genres")
        .eq("talent_id", tid)
        .limit(1);
      if (rows.data && rows.data[0]) {
        Object.assign(profile, rows.data[0], { talent_id: tid });
      }
    }
  } catch (err) {
    console.error("profile error:", err.message);
  }
  res.json({ profile });
});

app.get(["/programs", "/talents", "/politicians"], (_req, res) => {
  res.sendFile(path.join(__dirname, "public", "index.html"));
});

app.listen(PORT, "0.0.0.0", () => {
  console.log(`tclip-search: http://localhost:${PORT}`);
});
