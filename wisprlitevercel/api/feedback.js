// Vercel serverless function: POST /api/feedback
// Emails user-submitted feedback to the maintainer via Resend. USER-INITIATED only
// (the desktop app sends this when the user clicks Send) — never background telemetry.
//
// Required env: RESEND_API_KEY
// Optional env:
//   FEEDBACK_TO    where feedback is emailed (default james@powleads.com)
//   FEEDBACK_FROM  Resend "from" (default "PipeVoice <onboarding@resend.dev>" — works
//                  with NO verified domain when the recipient is the Resend account
//                  owner; switch to e.g. "PipeVoice <feedback@pipevoice.app>" once
//                  that domain is a verified Resend sender)
//   ALLOWED_ORIGINS  extra browser origins to accept
//
// The app is open source, so a baked-in client secret would be public and pointless.
// Abuse protection here = honeypot + length caps; enable Vercel Firewall rate-limit
// rules (dashboard, no code) before this sees real traffic.

const CATEGORIES = new Set(["bug", "idea", "other"]);
const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const MAX_MSG = 5000, MAX_META = 120, MAX_EMAIL = 254;

const DEFAULT_ORIGINS = [
  "https://pipevoice.app", "https://www.pipevoice.app", "https://pipevoice.vercel.app",
];
function originAllowed(req) {
  const origin = req.headers.origin;
  if (!origin) return true; // desktop app / non-browser — no Origin header
  try {
    const host = new URL(origin).hostname;
    if (host === "localhost" || host === "127.0.0.1") return true;
    if (host.endsWith("-powleads-projects.vercel.app")) return true; // preview deploys
    const extra = (process.env.ALLOWED_ORIGINS || "").split(",").map((s) => s.trim()).filter(Boolean);
    return new Set([...DEFAULT_ORIGINS, ...extra]).has(origin);
  } catch { return false; }
}

export function validateFeedback(body) {
  if (body && body.website) return { drop: true }; // honeypot
  const message = String((body && body.message) || "").trim().slice(0, MAX_MSG);
  if (message.length < 2) return { error: "empty_message" };
  let category = String((body && body.category) || "").trim().toLowerCase();
  if (!CATEGORIES.has(category)) category = "other";
  let email = String((body && body.email) || "").trim().toLowerCase().slice(0, MAX_EMAIL);
  if (email && !EMAIL_RE.test(email)) email = ""; // ignore a bad email rather than reject the feedback
  const appVersion = String((body && body.app_version) || "").trim().slice(0, MAX_META);
  const os = String((body && body.os) || "").trim().slice(0, MAX_META);
  return { ok: true, message, category, email, appVersion, os };
}

export function buildEmail(f, to, from) {
  const subject = `[PipeVoice · ${f.category}] ${f.message.slice(0, 60).replace(/\s+/g, " ")}`;
  const text = [
    f.message, "", "—",
    `category: ${f.category}`,
    `from: ${f.email || "(no email given)"}`,
    `app: ${f.appVersion || "?"}`,
    `os: ${f.os || "?"}`,
  ].join("\n");
  const payload = { from, to: [to], subject, text };
  if (f.email) payload.reply_to = f.email;
  return payload;
}

export default async function handler(req, res) {
  if (req.method === "OPTIONS") return res.status(204).end();
  if (req.method !== "POST") return res.status(405).json({ error: "method_not_allowed" });
  if (!originAllowed(req)) return res.status(403).json({ error: "forbidden" });

  const body =
    typeof req.body === "string" ? safeJson(req.body)
    : req.body && typeof req.body === "object" && !Array.isArray(req.body) ? req.body : {};

  const v = validateFeedback(body);
  if (v.drop) return res.status(200).json({ ok: true }); // honeypot: feign success
  if (v.error) return res.status(400).json({ error: v.error });

  const key = process.env.RESEND_API_KEY;
  if (!key) { console.error("feedback: missing RESEND_API_KEY"); return res.status(500).json({ error: "server_error" }); }
  const to = process.env.FEEDBACK_TO || "james@powleads.com";
  const from = process.env.FEEDBACK_FROM || "PipeVoice <onboarding@resend.dev>";

  try {
    const r = await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
      body: JSON.stringify(buildEmail(v, to, from)),
    });
    if (!r.ok) {
      const detail = await r.text().catch(() => "");
      console.error(`feedback: Resend send failed ${r.status}: ${detail.slice(0, 200)}`);
      return res.status(502).json({ error: "provider_error" });
    }
  } catch (err) {
    console.error("feedback: Resend send threw:", err);
    return res.status(502).json({ error: "provider_error" });
  }
  return res.status(200).json({ ok: true });
}

function safeJson(s) { try { const v = JSON.parse(s); return v && typeof v === "object" && !Array.isArray(v) ? v : {}; } catch { return {}; } }
