// Vercel serverless function: POST /api/subscribe
// Adds an email to a Resend Audience (master), and also to an ICP audience
// when the role is one SignalEngine sells to (founder / agency / sales).
//
// Required env (Vercel → Project → Settings → Environment Variables):
//   RESEND_API_KEY          your Resend key
//   RESEND_AUDIENCE_ID      "master" audience (everyone — app updates)
// Optional env:
//   RESEND_ICP_AUDIENCE_ID  ICP audience (founder / agency / sales)
//   ALLOWED_ORIGINS         comma-separated extra origins to accept (e.g. https://pipevoice.app)
//
// Abuse protection out of the box is a honeypot field + an Origin allowlist —
// both cheap and not bulletproof. Before this endpoint gets real traffic, turn on
// Vercel Firewall rate-limit rules (dashboard, no code change). If you later want a
// CAPTCHA, wire Cloudflare Turnstile END TO END (widget + sitekey on the form AND a
// server-side verify here) — don't add a server check without the widget, or every
// real signup fails.

const ICP_ROLES = new Set(["founder", "agency", "sales"]);
const ROLES = new Set(["founder", "agency", "sales", "developer", "writer", "other", ""]);
const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

// Origins always accepted (prod + local dev); add more via ALLOWED_ORIGINS.
const DEFAULT_ORIGINS = [
  "https://pipevoice.vercel.app",
  "https://pipevoice.app",
  "https://www.pipevoice.app",
  "https://wisprlite.vercel.app", // legacy, pre-rename
];

function originAllowed(req) {
  const origin = req.headers.origin;
  if (!origin) return true; // no Origin header (non-browser) — other layers still apply
  try {
    const host = new URL(origin).hostname;
    if (host === "localhost" || host === "127.0.0.1") return true;
    if (host === "pipevoice.vercel.app" || host === "pipevoice.app" || host === "www.pipevoice.app") return true;
    if (host === "wisprlite.vercel.app") return true; // legacy, pre-rename
    if (host.endsWith("-powleads-projects.vercel.app")) return true; // preview deploys
    const extra = (process.env.ALLOWED_ORIGINS || "")
      .split(",").map((s) => s.trim()).filter(Boolean);
    return new Set([...DEFAULT_ORIGINS, ...extra]).has(origin);
  } catch {
    return false;
  }
}

export default async function handler(req, res) {
  if (req.method === "OPTIONS") return res.status(204).end();
  if (req.method !== "POST") {
    return res.status(405).json({ error: "method_not_allowed" });
  }
  if (!originAllowed(req)) {
    return res.status(403).json({ error: "forbidden" });
  }

  const body =
    typeof req.body === "string"
      ? safeJson(req.body)
      : req.body && typeof req.body === "object" && !Array.isArray(req.body)
      ? req.body
      : {};

  // honeypot: bots fill hidden fields; humans don't (kept as a cheap pre-filter)
  if (body.website) return res.status(200).json({ ok: true });

  const email = String(body.email || "").trim().toLowerCase().slice(0, 254);
  let role = String(body.role || "").trim().toLowerCase();
  if (!ROLES.has(role)) role = "other";

  if (!EMAIL_RE.test(email)) {
    return res.status(400).json({ error: "invalid_email" });
  }

  const key = process.env.RESEND_API_KEY;
  const master = process.env.RESEND_AUDIENCE_ID;
  const icp = process.env.RESEND_ICP_AUDIENCE_ID;
  if (!key || !master) {
    // Don't leak config state to the client; log for ourselves.
    console.error("subscribe: missing RESEND_API_KEY or RESEND_AUDIENCE_ID");
    return res.status(500).json({ error: "server_error" });
  }

  const addTo = (audienceId) =>
    fetch(`https://api.resend.com/audiences/${audienceId}/contacts`, {
      method: "POST",
      headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
      body: JSON.stringify({ email, unsubscribed: false }),
    });

  // Master add is the one that must succeed. fetch() does NOT reject on HTTP
  // 4xx/5xx, so we MUST inspect res.ok — otherwise a bad key (401) or a
  // rate-limit (429) would silently look like success. 409 = already a
  // contact, which is fine (idempotent re-signup).
  try {
    const r = await addTo(master);
    if (!r.ok && r.status !== 409) {
      const detail = await r.text().catch(() => "");
      console.error(`subscribe: Resend master add failed ${r.status}: ${detail.slice(0, 200)}`);
      return res.status(502).json({ error: "provider_error" });
    }
  } catch (err) {
    console.error("subscribe: Resend master add threw:", err);
    return res.status(502).json({ error: "provider_error" });
  }

  // ICP add is best-effort: master already succeeded, so a failure here must
  // NOT fail the whole request (the user IS subscribed).
  if (icp && ICP_ROLES.has(role)) {
    try {
      const r = await addTo(icp);
      if (!r.ok && r.status !== 409) {
        console.error(`subscribe: Resend ICP add failed ${r.status}`);
      }
    } catch (err) {
      console.error("subscribe: Resend ICP add threw:", err);
    }
  }

  return res.status(200).json({ ok: true });
}

function safeJson(s) {
  try {
    const v = JSON.parse(s);
    return v && typeof v === "object" && !Array.isArray(v) ? v : {};
  } catch {
    return {};
  }
}
