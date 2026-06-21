// Vercel serverless function: POST /api/track
// First-party, cookieless, aggregate-only pageview counter. It stores NO IP
// address and NO personal data. Unique-visitor estimates use a daily-rotating
// salted hash fed into a Redis HyperLogLog (PFADD), which keeps no identifiers
// and cannot be reversed or used to track anyone across days.
//
// No-op (returns 204) unless Upstash Redis is configured, so the site works
// fine without it. Required env to enable:
//   UPSTASH_REDIS_REST_URL    Upstash Redis REST URL
//   UPSTASH_REDIS_REST_TOKEN  Upstash Redis REST token
// Optional env:
//   ANALYTICS_SALT            hash salt (defaults to ADMIN_TOKEN, else a constant)

import crypto from "node:crypto";

const KEEP_DAYS = 120;

export default async function handler(req, res) {
  if (req.method === "OPTIONS") return res.status(204).end();
  if (req.method !== "POST") return res.status(405).json({ error: "method_not_allowed" });

  const url = process.env.UPSTASH_REDIS_REST_URL;
  const token = process.env.UPSTASH_REDIS_REST_TOKEN;
  if (!url || !token) return res.status(204).end(); // analytics not configured -> silent no-op

  const body =
    typeof req.body === "string"
      ? safe(req.body)
      : req.body && typeof req.body === "object" && !Array.isArray(req.body)
      ? req.body
      : {};

  let path = String(body.p || "/").trim().replace(/[\r\n]/g, "");
  if (!path.startsWith("/")) path = "/";
  path = path.slice(0, 120);

  const date = new Date().toISOString().slice(0, 10);
  const ip = String(req.headers["x-forwarded-for"] || "").split(",")[0].trim();
  const ua = String(req.headers["user-agent"] || "").slice(0, 200);
  const salt = process.env.ANALYTICS_SALT || process.env.ADMIN_TOKEN || "pipevoice";
  // One-way, daily-rotating, salted. We feed ONLY this digest into a HyperLogLog;
  // the raw IP/UA are never stored anywhere.
  const visitor = crypto.createHash("sha256").update(`${ip}|${ua}|${date}|${salt}`).digest("hex");

  let refHost = "";
  try {
    const r = String(body.r || "");
    if (r) {
      const h = new URL(r).hostname;
      if (h && h !== "localhost" && h !== "127.0.0.1" && !/(^|\.)pipevoice\.app$/.test(h)) {
        refHost = h.slice(0, 100);
      }
    }
  } catch {}

  const cmds = [
    ["INCR", "pv:total"],
    ["INCR", `pv:day:${date}`],
    ["EXPIRE", `pv:day:${date}`, KEEP_DAYS * 86400],
    ["HINCRBY", "pv:paths", path, 1],
    ["PFADD", `uv:day:${date}`, visitor],
    ["EXPIRE", `uv:day:${date}`, KEEP_DAYS * 86400],
    ["PFADD", "uv:all", visitor],
  ];
  if (refHost) cmds.push(["HINCRBY", "pv:refs", refHost, 1]);

  // First-party campaign attribution: aggregate counts of utm_* tags in the
  // link the visitor followed. No PII; same first-party endpoint, no pixels.
  const clean = (s) => String(s || "").toLowerCase().trim().replace(/[\r\n]/g, "").slice(0, 80);
  const src = clean(body.utm_source), med = clean(body.utm_medium), camp = clean(body.utm_campaign);
  if (src) cmds.push(["HINCRBY", "utm:source", src, 1]);
  if (med) cmds.push(["HINCRBY", "utm:medium", med, 1]);
  if (camp) cmds.push(["HINCRBY", "utm:campaign", camp, 1]);

  try {
    await fetch(`${url}/pipeline`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify(cmds),
    });
  } catch {
    // analytics is best-effort; never let it surface to the visitor
  }
  return res.status(204).end();
}

function safe(s) {
  try {
    const v = JSON.parse(s);
    return v && typeof v === "object" && !Array.isArray(v) ? v : {};
  } catch {
    return {};
  }
}
