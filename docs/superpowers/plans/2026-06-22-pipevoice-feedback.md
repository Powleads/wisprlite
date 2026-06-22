# In-app Feedback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use `- [ ]` checkboxes.

**Goal:** A user-initiated "Send feedback" feature in the PipeVoice tray app — a small dialog (bug / idea / other + message + optional reply email) that POSTs to a new Vercel function which emails the maintainer via Resend, plus a "prefer GitHub?" link. Approved design (brainstormed): in-app form → inbox + GitHub link.

**Architecture:** Tray "Send feedback…" → spawns `feedback.py` (separate-process Tk window, like `--about`) → POSTs JSON to `https://pipevoice.app/api/feedback` (stdlib `urllib`, no new dep) → `api/feedback.js` (mirrors `api/subscribe.js`) validates + sends an email via Resend to the maintainer, `reply_to` = the user's email. User-initiated only; the dialog discloses exactly what's sent (message + app version + OS — no audio/transcripts).

**Tech stack:** Vercel serverless (ESM, Resend `/emails` via fetch), Python stdlib (`urllib`, `tkinter`), Node 24 available for testing the function's pure validation.

**Key decisions:** PipeVoice is open source → a client secret is meaningless (public), so abuse protection = honeypot + length caps + (recommend) Vercel Firewall rate-limit; no Turnstile (no browser widget on a desktop POST). Resend `from` defaults to `onboarding@resend.dev` (works with no verified domain when sending to the Resend account owner) → set `FEEDBACK_FROM` to a branded address once `pipevoice.app` is a verified Resend sender. No ticketing system — the reply-email IS the support loop.

**Branch:** `feat/in-app-feedback` (off main, which has all prior PRs merged).

---

## Task 1: Vercel function `api/feedback.js` (+ node test)

**Files:** Create `wisprlitevercel/api/feedback.js`, `tests/test_feedback_api.mjs`

- [ ] **Step 1: failing test** — create `tests/test_feedback_api.mjs`:

```js
import assert from "node:assert";
import { validateFeedback, buildEmail } from "../wisprlitevercel/api/feedback.js";

// honeypot -> drop
assert.deepEqual(validateFeedback({ website: "x", message: "hi" }), { drop: true });
// empty message -> error
assert.equal(validateFeedback({ message: " " }).error, "empty_message");
// valid: trims, normalizes unknown category to "other", drops a bad email (doesn't reject)
const v = validateFeedback({ message: "  it crashed  ", category: "ZZZ", email: "nope", app_version: "2.26.0", os: "Win11" });
assert.equal(v.ok, true); assert.equal(v.message, "it crashed"); assert.equal(v.category, "other");
assert.equal(v.email, ""); assert.equal(v.appVersion, "2.26.0"); assert.equal(v.os, "Win11");
// known category kept; good email lowercased + reply_to set; subject + to correct
const v2 = validateFeedback({ message: "add dark mode", category: "idea", email: "A@B.com" });
assert.equal(v2.category, "idea"); assert.equal(v2.email, "a@b.com");
const mail = buildEmail(v2, "james@powleads.com", "PipeVoice <onboarding@resend.dev>");
assert.equal(mail.reply_to, "a@b.com"); assert.deepEqual(mail.to, ["james@powleads.com"]);
assert.ok(mail.subject.startsWith("[PipeVoice · idea]")); assert.ok(mail.text.includes("add dark mode"));
// message length cap
assert.equal(validateFeedback({ message: "x".repeat(9000) }).message.length, 5000);
console.log("OK");
```

Run: `node tests/test_feedback_api.mjs` → Expected FAIL: `Cannot find module '.../api/feedback.js'`.

- [ ] **Step 2: implement** — create `wisprlitevercel/api/feedback.js`:

```js
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
```

- [ ] **Step 3: pass** — `node tests/test_feedback_api.mjs` → `OK`. Also `node --check wisprlitevercel/api/feedback.js`.
- [ ] **Step 4: commit** — `git add wisprlitevercel/api/feedback.js tests/test_feedback_api.mjs && git commit -m "feat(feedback): api/feedback.js — Resend-email feedback endpoint"`

---

## Task 2: the dialog `feedback.py`

**Files:** Create `wisprlite/feedback.py`. Mirrors `about.py` (separate-process Tk window, dark/coral theme, `winui.dark_titlebar`).

- [ ] **Step 1: implement** — create `wisprlite/feedback.py`:

```python
"""Send feedback: a small window that POSTs user feedback to the site's
/api/feedback (which emails the maintainer via Resend). User-initiated only —
launched as its own process via ``--feedback`` (like --about)."""

from __future__ import annotations

import json
import platform
import threading
import urllib.request
import webbrowser

from . import __version__, config

BG = "#13151d"; CARD = "#1b1e29"; FG = "#e5e7eb"; MUTED = "#94a3b8"
ACCENT = "#e06c75"; GOOD = "#98c379"; WARN = "#e5c07b"
ENDPOINT = "https://pipevoice.app/api/feedback"
ISSUES_URL = "https://github.com/Powleads/PipeVoice/issues/new"
CATEGORIES = [("bug", "Bug / something broke"), ("idea", "Feature idea"), ("other", "Something else")]


def _post(payload: dict):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(ENDPOINT, data=data,
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return (200 <= r.status < 300, "")
    except Exception as exc:
        return (False, str(exc))


def main() -> None:
    try:
        import tkinter as tk
        from tkinter import ttk
    except Exception:
        return
    from . import winui

    root = tk.Tk(); root.title("Send feedback — Pipevoice"); root.configure(bg=BG); root.resizable(False, False)
    ico = config.asset_path("wisprlite.ico")
    if ico:
        try: root.iconbitmap(ico)
        except Exception: pass

    style = ttk.Style(root)
    try: style.theme_use("clam")
    except Exception: pass
    style.configure("Accent.TButton", background=ACCENT, foreground="#1a0c0d",
                    font=("Segoe UI", 9, "bold"), padding=8, borderwidth=0)
    style.map("Accent.TButton", background=[("active", "#e8838b")])
    style.configure("TCombobox", fieldbackground=CARD, background=CARD, foreground=FG, arrowcolor=MUTED)

    wrap = tk.Frame(root, bg=BG, padx=26, pady=22); wrap.pack(fill="both", expand=True)
    tk.Label(wrap, text="Send feedback", bg=BG, fg=FG, font=("Segoe UI", 15, "bold")).pack(anchor="w")
    tk.Label(wrap, text="Found a bug or want a feature? Tell me — it goes straight to my inbox.",
             bg=BG, fg=MUTED, font=("Segoe UI", 9), wraplength=430, justify="left").pack(anchor="w", pady=(2, 14))

    tk.Label(wrap, text="Type", bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w")
    cat_var = tk.StringVar(value=CATEGORIES[0][1])
    ttk.Combobox(wrap, textvariable=cat_var, state="readonly",
                 values=[l for _, l in CATEGORIES], width=32).pack(anchor="w", pady=(2, 12))

    tk.Label(wrap, text="Message", bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w")
    msg = tk.Text(wrap, height=6, width=54, bg=CARD, fg=FG, insertbackground=FG,
                  relief="flat", font=("Segoe UI", 10), wrap="word")
    msg.pack(anchor="w", pady=(2, 12))

    tk.Label(wrap, text="Your email (optional — only if you'd like a reply)",
             bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w")
    email = tk.Entry(wrap, bg=CARD, fg=FG, insertbackground=FG, relief="flat", font=("Segoe UI", 10), width=54)
    email.pack(anchor="w", pady=(2, 10), ipady=4)

    tk.Label(wrap, text=f"Sends your message + PipeVoice {__version__} + your Windows version. "
                        "Nothing else — no audio, no transcripts — and only when you click Send.",
             bg=BG, fg=MUTED, font=("Segoe UI", 8), wraplength=430, justify="left").pack(anchor="w", pady=(0, 12))

    status = tk.Label(wrap, text="", bg=BG, fg=MUTED, font=("Segoe UI", 9)); status.pack(anchor="w")

    row = tk.Frame(wrap, bg=BG); row.pack(fill="x", pady=(8, 0))
    send_btn = ttk.Button(row, text="Send", style="Accent.TButton"); send_btn.pack(side="left")
    gh = tk.Label(row, text="Prefer GitHub? Open an issue ↗", bg=BG, fg=ACCENT, cursor="hand2",
                  font=("Segoe UI", 9, "underline")); gh.pack(side="left", padx=(14, 0))
    gh.bind("<Button-1>", lambda e: webbrowser.open(ISSUES_URL))

    def do_send():
        text = msg.get("1.0", "end").strip()
        if len(text) < 2:
            status.config(text="Please type a message first.", fg=WARN); return
        label = cat_var.get()
        category = next((c for c, l in CATEGORIES if l == label), "other")
        payload = {"category": category, "message": text, "email": email.get().strip(),
                   "app_version": __version__, "os": platform.platform()}
        send_btn.config(state="disabled"); status.config(text="Sending…", fg=MUTED)

        def work():
            ok, _err = _post(payload)

            def done():
                if ok:
                    status.config(text="Thanks — sent. 🙏", fg=GOOD); send_btn.config(text="Sent")
                    root.after(1200, root.destroy)
                else:
                    status.config(text="Couldn't send — check your connection, or use GitHub.", fg=WARN)
                    send_btn.config(state="normal")
            root.after(0, done)
        threading.Thread(target=work, daemon=True).start()
    send_btn.config(command=do_send)

    root.update_idletasks()
    w = max(500, root.winfo_reqwidth()); h = root.winfo_reqheight()
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 3}")
    winui.dark_titlebar(root)
    root.mainloop()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: verify** — `python3 -c "import ast; ast.parse(open('wisprlite/feedback.py').read()); print('ok')"` → `ok`. (Can't run Tk headless on Linux — see manual verify in Task 4.)
- [ ] **Step 3: commit** — `git add wisprlite/feedback.py && git commit -m "feat(feedback): the Send feedback dialog (feedback.py)"`

---

## Task 3: wiring (flags, tray, About link, privacy)

**Files:** Modify `wisprlite/__main__.py`, `launch.py`, `wisprlite/app.py`, `wisprlite/tray.py`, `wisprlite/about.py`, `wisprlitevercel/privacy.html`

- [ ] **Step 1: `--feedback` flag in both entry points.**
  `wisprlite/__main__.py` — after the `elif "--mcp" in sys.argv:` branch, before `else:`:
  ```python
  elif "--feedback" in sys.argv:
      from .feedback import main
  ```
  `launch.py` — after its `elif "--mcp" in sys.argv:` branch, before `else:`:
  ```python
  elif "--mcp" in sys.argv:
      from wisprlite.mcp_shim import main
  elif "--feedback" in sys.argv:
      from wisprlite.feedback import main
  ```
  (Keep the existing `--mcp` line; just add the `--feedback` elif after it.)

- [ ] **Step 2: `App.open_feedback()`** — in `wisprlite/app.py`, add after `open_about` (mirrors it):
  ```python
  def open_feedback(self) -> None:
      import os
      import subprocess

      try:
          if getattr(sys, "frozen", False):
              subprocess.Popen([sys.executable, "--feedback"])
          else:
              from .autostart import _pythonw

              parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
              subprocess.Popen([_pythonw(), "-m", "wisprlite", "--feedback"], cwd=parent)
      except Exception as exc:
          self._fail(f"feedback: {exc}")
  ```

- [ ] **Step 3: tray menu item** — in `wisprlite/tray.py`, after the `Item("About / What's new…", ...)` line, add:
  ```python
            Item("Send feedback…", lambda i, it: app.open_feedback()),
  ```

- [ ] **Step 4: About-dialog link** — in `wisprlite/about.py` `build()`, the `actions` frame already has a `link` ("All releases ↗"). Right after that `link.bind(...)` line, add a second link:
  ```python
      fb = tk.Label(actions, text="Send feedback ↗", bg=BG, fg=ACCENT, cursor="hand2",
                    font=("Segoe UI", 9, "underline"))
      fb.pack(side="left", padx=(16, 0))
      fb.bind("<Button-1>", lambda e: _open_feedback())
  ```
  And add this helper near the top of `about.py` (module level, after the imports):
  ```python
  def _open_feedback() -> None:
      import os
      import subprocess
      import sys
      try:
          if getattr(sys, "frozen", False):
              subprocess.Popen([sys.executable, "--feedback"])
          else:
              from .autostart import _pythonw
              parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
              subprocess.Popen([_pythonw(), "-m", "wisprlite", "--feedback"], cwd=parent)
      except Exception:
          pass
  ```

- [ ] **Step 5: privacy disclosure** — in `wisprlitevercel/privacy.html`, add a short paragraph (match the page's existing markup — read it and mirror the surrounding `<p>`/heading style). Content:
  > **Feedback you send.** If you use *Send feedback* in the app, the message you type — plus your PipeVoice version and Windows version, and your email only if you choose to enter one — is sent to us so we can read and reply to it. Nothing is sent unless you click Send; we never transmit your audio or transcripts.

- [ ] **Step 6: verify + commit** — `python3 -c "import ast; ast.parse(open('wisprlite/app.py').read()); ast.parse(open('wisprlite/tray.py').read()); ast.parse(open('wisprlite/about.py').read()); ast.parse(open('wisprlite/__main__.py').read()); ast.parse(open('launch.py').read()); print('ok')"` → `ok`; `node tests/test_feedback_api.mjs` still `OK`.
  `git add -A && git commit -m "feat(feedback): wire --feedback flag, tray + About entry points, privacy disclosure"`

---

## Manual verification (Windows — can't run Tk/Vercel here)
- [ ] Set Vercel env `RESEND_API_KEY` (exists) — feedback works once deployed; optionally set `FEEDBACK_FROM` to a verified `pipevoice.app` sender (else it uses `onboarding@resend.dev` → delivers to the Resend account owner = james@).
- [ ] Tray → "Send feedback…" opens the dialog; the About dialog shows the "Send feedback ↗" link.
- [ ] Type a message, pick a category, (optionally) an email → Send → arrives at james@ with the right subject + reply-to; the version/OS are included; no audio/transcript.
- [ ] Empty message is blocked client-side; a send failure shows the GitHub fallback.
- [ ] Confirm `api/feedback.js` deployed (POST to https://pipevoice.app/api/feedback returns `{ok:true}` for a valid body).

## Self-review
- Spec coverage: dialog (T2) + endpoint (T1) + GitHub link (T2) + tray/About entry (T3) + privacy disclosure (T3.5) + version/OS auto-include disclosed (T2). ✔
- No client secret (OSS) — documented; abuse = honeypot + caps + Vercel Firewall note. ✔
- No new Python dep (stdlib urllib). New endpoint reuses RESEND_API_KEY. ✔
- Out of scope (deferred): log-file attach, in-app reply threads, settings fields.
