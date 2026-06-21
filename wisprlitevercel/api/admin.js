// Vercel serverless function: GET /api/admin
// Returns dashboard stats for admin.html. Gated by ADMIN_TOKEN (sent as the
// `x-admin-token` header, or `Authorization: Bearer <token>`).
//
// Required env:
//   ADMIN_TOKEN              the dashboard password (if unset, the API is disabled)
// For subscriber counts:
//   RESEND_API_KEY, RESEND_AUDIENCE_ID, [RESEND_ICP_AUDIENCE_ID]
// For visitor counts:
//   UPSTASH_REDIS_REST_URL, UPSTASH_REDIS_REST_TOKEN
// Optional:
//   GITHUB_TOKEN            raises the GitHub API rate limit (public repo works without)

import crypto from "node:crypto";

const REPO = "Powleads/PipeVoice";
const ASSET = "Pipevoice-Setup.exe";

export default async function handler(req, res) {
  res.setHeader("Cache-Control", "no-store");
  if (req.method !== "GET") return res.status(405).json({ error: "method_not_allowed" });

  const expected = process.env.ADMIN_TOKEN;
  if (!expected) return res.status(503).json({ error: "admin_not_configured" });
  const given = String(
    req.headers["x-admin-token"] || (req.headers.authorization || "").replace(/^Bearer\s+/i, "")
  );
  if (!tokenOk(given, expected)) return res.status(401).json({ error: "unauthorized" });

  const [downloads, subscribers, visitors] = await Promise.all([
    getDownloads().catch((e) => ({ error: String(e && e.message || e) })),
    getSubscribers().catch((e) => ({ error: String(e && e.message || e) })),
    getVisitors().catch((e) => ({ error: String(e && e.message || e) })),
  ]);
  return res.status(200).json({ generatedAt: new Date().toISOString(), downloads, subscribers, visitors });
}

function tokenOk(a, b) {
  const ba = Buffer.from(String(a));
  const bb = Buffer.from(String(b));
  if (ba.length !== bb.length) return false;
  try {
    return crypto.timingSafeEqual(ba, bb);
  } catch {
    return false;
  }
}

async function getDownloads() {
  const headers = { "User-Agent": "pipevoice-admin", Accept: "application/vnd.github+json" };
  if (process.env.GITHUB_TOKEN) headers.Authorization = `Bearer ${process.env.GITHUB_TOKEN}`;
  const r = await fetch(`https://api.github.com/repos/${REPO}/releases?per_page=100`, { headers });
  if (!r.ok) throw new Error(`github ${r.status}`);
  const releases = await r.json();
  let total = 0;
  const byVersion = [];
  for (const rel of releases) {
    const asset = (rel.assets || []).find((a) => a.name === ASSET);
    const count = asset ? asset.download_count : 0;
    total += count;
    byVersion.push({
      tag: rel.tag_name,
      downloads: count,
      publishedAt: rel.published_at,
      latest: false,
    });
  }
  if (byVersion.length) byVersion[0].latest = true; // GitHub returns releases newest-first
  return { total, latest: byVersion[0] ? byVersion[0].tag : null, byVersion };
}

async function getSubscribers() {
  const key = process.env.RESEND_API_KEY;
  const master = process.env.RESEND_AUDIENCE_ID;
  const icp = process.env.RESEND_ICP_AUDIENCE_ID;
  if (!key || !master) return { configured: false };
  const count = async (id) => {
    if (!id) return null;
    const r = await fetch(`https://api.resend.com/audiences/${id}/contacts`, {
      headers: { Authorization: `Bearer ${key}` },
    });
    if (!r.ok) throw new Error(`resend ${r.status}`);
    const j = await r.json();
    const list = Array.isArray(j.data) ? j.data : [];
    return list.filter((c) => !c.unsubscribed).length;
  };
  return { configured: true, total: await count(master), icp: await count(icp) };
}

async function getVisitors() {
  const url = process.env.UPSTASH_REDIS_REST_URL;
  const token = process.env.UPSTASH_REDIS_REST_TOKEN;
  if (!url || !token) return { configured: false };

  const days = [];
  for (let i = 6; i >= 0; i--) {
    days.push(new Date(Date.now() - i * 86400000).toISOString().slice(0, 10));
  }
  const cmds = [
    ["GET", "pv:total"],
    ["PFCOUNT", "uv:all"],
    ["HGETALL", "pv:paths"],
    ["HGETALL", "pv:refs"],
    ["HGETALL", "utm:source"],
    ["HGETALL", "utm:medium"],
    ["HGETALL", "utm:campaign"],
  ];
  for (const d of days) {
    cmds.push(["GET", `pv:day:${d}`]);
    cmds.push(["PFCOUNT", `uv:day:${d}`]);
  }
  const r = await fetch(`${url}/pipeline`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify(cmds),
  });
  if (!r.ok) throw new Error(`upstash ${r.status}`);
  const out = await r.json();
  const val = (i) => (out[i] && typeof out[i] === "object" && "result" in out[i] ? out[i].result : out[i]);

  const totalViews = Number(val(0) || 0);
  const uniqueAll = Number(val(1) || 0);
  const topPaths = pairs(val(2)).sort((a, b) => b[1] - a[1]).slice(0, 12).map(([path, views]) => ({ path, views }));
  const topRefs = pairs(val(3)).sort((a, b) => b[1] - a[1]).slice(0, 12).map(([host, views]) => ({ host, views }));
  const topSources = pairs(val(4)).sort((a, b) => b[1] - a[1]).slice(0, 12).map(([source, views]) => ({ source, views }));
  const topMediums = pairs(val(5)).sort((a, b) => b[1] - a[1]).slice(0, 12).map(([medium, views]) => ({ medium, views }));
  const topCampaigns = pairs(val(6)).sort((a, b) => b[1] - a[1]).slice(0, 12).map(([campaign, views]) => ({ campaign, views }));

  const last7 = [];
  let idx = 7;
  for (const d of days) {
    const views = Number(val(idx++) || 0);
    const uniques = Number(val(idx++) || 0);
    last7.push({ date: d, views, uniques });
  }
  return { configured: true, totalViews, uniqueAll, last7, topPaths, topRefs, topSources, topMediums, topCampaigns };
}

function pairs(h) {
  if (!h) return [];
  if (Array.isArray(h)) {
    const out = [];
    for (let i = 0; i < h.length; i += 2) out.push([h[i], Number(h[i + 1] || 0)]);
    return out;
  }
  if (typeof h === "object") return Object.entries(h).map(([k, v]) => [k, Number(v || 0)]);
  return [];
}
