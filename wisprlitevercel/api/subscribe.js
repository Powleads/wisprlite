// Vercel serverless function: POST /api/subscribe
// Adds an email to a Resend Audience (master), and also to an ICP audience
// when the role is one SignalEngine sells to (founder / agency / sales).
//
// Env vars (set in Vercel → Project → Settings → Environment Variables):
//   RESEND_API_KEY          your Resend key
//   RESEND_AUDIENCE_ID      "master" audience (everyone — app updates)
//   RESEND_ICP_AUDIENCE_ID  ICP audience (founder/agency/sales) [optional]

const ICP_ROLES = new Set(["founder", "agency", "sales"]);
const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

export default async function handler(req, res) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "method_not_allowed" });
  }

  const body = typeof req.body === "string" ? safeJson(req.body) : (req.body || {});
  const email = (body.email || "").trim().toLowerCase();
  const role = (body.role || "").trim().toLowerCase();

  // honeypot: bots fill hidden fields; humans don't
  if (body.website) return res.status(200).json({ ok: true });

  if (!EMAIL_RE.test(email)) {
    return res.status(400).json({ error: "invalid_email" });
  }

  const key = process.env.RESEND_API_KEY;
  const master = process.env.RESEND_AUDIENCE_ID;
  const icp = process.env.RESEND_ICP_AUDIENCE_ID;
  if (!key || !master) {
    return res.status(500).json({ error: "not_configured" });
  }

  const addTo = (audienceId) =>
    fetch(`https://api.resend.com/audiences/${audienceId}/contacts`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${key}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ email, unsubscribed: false }),
    });

  try {
    await addTo(master);
    if (icp && ICP_ROLES.has(role)) await addTo(icp);
    return res.status(200).json({ ok: true });
  } catch (err) {
    return res.status(502).json({ error: "provider_error" });
  }
}

function safeJson(s) {
  try {
    return JSON.parse(s);
  } catch {
    return {};
  }
}
