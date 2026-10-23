// Anthropic token usage vs. cost dashboard. No dependencies; Node 18+.
// Holds the Admin API key server-side, normalizes the Usage & Cost APIs, caches results.
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const PORT = process.env.PORT || 3000;
const ADMIN_KEY = process.env.ANTHROPIC_ADMIN_KEY;
const BASE = process.env.ANTHROPIC_ADMIN_BASE_URL || "https://api.anthropic.com";
const DEMO = process.env.DEMO === "1" || !ADMIN_KEY;
const CACHE_MS = 10 * 60 * 1000;
const PUBLIC = path.join(path.dirname(fileURLToPath(import.meta.url)), "public");

async function fetchAll(endpoint, params) {
  const out = [];
  let page;
  do {
    const qs = new URLSearchParams(params);
    if (page) qs.set("page", page);
    const res = await fetch(`${BASE}/v1/organizations/${endpoint}?${qs}`, {
      headers: { "x-api-key": ADMIN_KEY, "anthropic-version": "2023-06-01" },
    });
    if (!res.ok) throw new Error(`${endpoint} ${res.status}: ${await res.text()}`);
    const body = await res.json();
    out.push(...body.data);
    page = body.has_more ? body.next_page : null;
  } while (page);
  return out;
}

const day = (iso) => iso.slice(0, 10);

async function live(days) {
  const end = new Date();
  const start = new Date(end.getTime() - days * 86400000);
  start.setUTCHours(0, 0, 0, 0);
  const common = { starting_at: start.toISOString(), ending_at: end.toISOString(), bucket_width: "1d", limit: "31" };

  const [usage, cost] = await Promise.all([
    fetchAll("usage_report/messages", new URLSearchParams([...Object.entries(common), ["group_by[]", "model"]])),
    fetchAll("cost_report", new URLSearchParams([...Object.entries(common), ["group_by[]", "description"]])),
  ]);

  const byDay = new Map();
  const byModel = new Map();
  const get = (m, k, init) => (m.has(k) ? m.get(k) : (m.set(k, init), init));
  const blank = () => ({ uncached_input: 0, cache_write: 0, cache_read: 0, output: 0, cost_usd: 0 });

  for (const b of usage) {
    const d = get(byDay, day(b.starting_at), { date: day(b.starting_at), ...blank() });
    for (const r of b.results) {
      const m = get(byModel, r.model || "unknown", { model: r.model || "unknown", ...blank() });
      const cw = (r.cache_creation?.ephemeral_1h_input_tokens || 0) + (r.cache_creation?.ephemeral_5m_input_tokens || 0);
      for (const t of [d, m]) {
        t.uncached_input += r.uncached_input_tokens || 0;
        t.cache_write += cw;
        t.cache_read += r.cache_read_input_tokens || 0;
        t.output += r.output_tokens || 0;
      }
    }
  }
  for (const b of cost) {
    const d = get(byDay, day(b.starting_at), { date: day(b.starting_at), ...blank() });
    for (const r of b.results) {
      // amount is a decimal string in cents
      const usd = parseFloat(r.amount) / 100;
      const m = get(byModel, r.model || "Non-token charges", { model: r.model || "Non-token charges", ...blank() });
      d.cost_usd += usd;
      m.cost_usd += usd;
    }
  }
  return pack(byDay, byModel, "live");
}

function pack(byDay, byModel, source) {
  const daysArr = [...byDay.values()].sort((a, b) => a.date.localeCompare(b.date));
  const models = [...byModel.values()].sort((a, b) => b.cost_usd - a.cost_usd);
  return { source, days: daysArr, models };
}

// Deterministic sample data so the UI can be developed/demoed without a key.
function demo(days) {
  const byDay = new Map(), byModel = new Map();
  const specs = [
    ["claude-opus-4", 15, 75, 18.75, 1.5, 0.4],
    ["claude-sonnet-4", 3, 15, 3.75, 0.3, 1],
    ["claude-haiku-4", 1, 5, 1.25, 0.1, 0.6],
  ]; // model, $/Min, $/Mout, $/Mcachewrite, $/Mcacheread, volume weight
  for (const [model] of specs) byModel.set(model, { model, uncached_input: 0, cache_write: 0, cache_read: 0, output: 0, cost_usd: 0 });
  for (let i = days - 1; i >= 0; i--) {
    const date = new Date(Date.now() - i * 86400000).toISOString().slice(0, 10);
    const row = { date, uncached_input: 0, cache_write: 0, cache_read: 0, output: 0, cost_usd: 0 };
    const wk = [0, 6].includes(new Date(date).getUTCDay()) ? 0.35 : 1;
    specs.forEach(([model, pi, po, pw, pr, w], k) => {
      const s = (days - i) * 7 + k * 13;
      const noise = 0.75 + 0.5 * Math.abs(Math.sin(s));
      const vol = 20e6 * w * wk * noise * (1 + (days - i) / days);
      const t = { uncached_input: vol * 0.3, cache_write: vol * 0.1, cache_read: vol * 1.4, output: vol * 0.08 };
      const usd = (t.uncached_input * pi + t.output * po + t.cache_write * pw + t.cache_read * pr) / 1e6;
      const m = byModel.get(model);
      for (const x of [row, m]) { for (const key in t) x[key] += Math.round(t[key]); x.cost_usd += usd; }
    });
    byDay.set(date, row);
  }
  return pack(byDay, byModel, "demo");
}

const cache = new Map();
async function getData(days) {
  const hit = cache.get(days);
  if (hit && Date.now() - hit.at < CACHE_MS) return hit.data;
  const data = DEMO ? demo(days) : await live(days);
  cache.set(days, { at: Date.now(), data });
  return data;
}

const TYPES = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css" };
http.createServer(async (req, res) => {
  const url = new URL(req.url, "http://x");
  if (url.pathname === "/api/usage") {
    const days = Math.min(Math.max(parseInt(url.searchParams.get("days")) || 30, 1), 93);
    try {
      res.writeHead(200, { "content-type": "application/json" }).end(JSON.stringify(await getData(days)));
    } catch (e) {
      res.writeHead(502, { "content-type": "application/json" }).end(JSON.stringify({ error: e.message }));
    }
    return;
  }
  const file = path.join(PUBLIC, url.pathname === "/" ? "index.html" : path.normalize(url.pathname).replace(/^(\.\.[/\\])+/, ""));
  if (!file.startsWith(PUBLIC) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) return res.writeHead(404).end("Not found");
  res.writeHead(200, { "content-type": TYPES[path.extname(file)] || "application/octet-stream" }).end(fs.readFileSync(file));
}).listen(PORT, () => console.log(`Dashboard on http://localhost:${PORT} (${DEMO ? "DEMO data" : "live Anthropic data"})`));
