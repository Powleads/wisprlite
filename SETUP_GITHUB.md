# Getting the one-click installer via GitHub Actions

GitHub's Windows servers build `Pipevoice-Setup.exe` for you. You never need
Python or any build tools — you just download the finished installer and click.

## Step 1 — create an empty repo (≈15 seconds)

1. Go to **https://github.com/new**
2. Repository name: **`wisprlite`**
3. Leave it **empty** — do NOT add a README, .gitignore, or license.
4. Click **Create repository**.

Then tell Claude "done" — Claude pushes the project into it and the build kicks
off automatically. (If Claude's push is blocked by permissions, use Step 2b.)

## Step 2b — push it yourself (only if Claude can't)

In the unzipped folder, run:

```bat
git init -b main
git add .
git commit -m "Pipevoice"
git remote add origin https://github.com/Powleads/wisprlite.git
git push -u origin main
```

(Needs Git installed: https://git-scm.com/download/win — or use GitHub Desktop.)

## Step 3 — download your installer

Every push builds it. To grab it:

- **Quick (artifact):** repo → **Actions** tab → click the latest green run →
  scroll to **Artifacts** → download **Pipevoice-Setup** → unzip →
  double-click `Pipevoice-Setup.exe`.
- **Permanent link (release):** repo → **Releases** → **Draft a new release** →
  pick a tag like `v0.3.1` → **Publish**. The workflow attaches
  `Pipevoice-Setup.exe` to the release, giving you a stable download URL you can
  bookmark or share.

## What the installer does

Double-click `Pipevoice-Setup.exe` → installs (per-user, no admin) → launches →
Pipevoice asks for your API key in a popup → you're dictating. The icon sits in
your system tray; right-click it for Settings.
