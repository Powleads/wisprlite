# Pipevoice SEO + GEO Plan

_Last updated: 2026-06-22. Owner: James. Goal: rank in Google AND get cited by AI answer engines for "voice typing / dictation on Windows", driving free downloads that feed the SignalEngine funnel._

## 1. The opportunity (honest read)

Pipevoice has a real, under-served wedge: **free + open-source + Windows-native + offline option + types into any app (incl. the terminal/Claude Code)**. The paid leaders (Wispr Flow) are Mac-first, cloud-only, and subscription. That gap is the whole SEO thesis: own "**free Windows voice typing**" and the long tail around it.

We are starting from near-zero authority (new domain, June 2026). SEO is a 3-6 month compounding play, not a launch-day spike. So the plan runs **two tracks in parallel**:
- **Now (weeks 0-4):** launch/directory/community traffic + backlinks to build domain authority fast.
- **Compounding (month 1+):** the content engine (blog) that ranks and gets AI-cited over time.

### KPIs to watch (set up the tools in §7)
- Indexed pages (Search Console) → target all blog + core pages indexed within 2-3 weeks.
- Referring domains (backlinks) → target 30+ in month 1 (directories + launch sites do most of this).
- Organic clicks + impressions (Search Console).
- AI citations: manually check ChatGPT/Perplexity/Google AI Overviews monthly for "free voice typing windows", "wispr flow alternative", etc.
- Downloads (GitHub release count) and email signups (the real business metric).

## 2. Keyword strategy: pillars + clusters

Three pillars, each a hub page with a cluster of supporting blog posts linking up to it.

**Pillar A — Windows voice typing (head term).** Hub: `/windows-voice-typing` (exists).
Cluster: how to dictate on Windows, free speech-to-text Windows, best free voice typing software, Windows Voice Access vs third-party, offline/private dictation, fix Windows dictation not working.

**Pillar B — Alternatives & comparisons (high-intent, fast wins).** Hub: `/vs/wispr-flow` (exists).
Cluster: Wispr Flow alternative (free), Dragon NaturallySpeaking alternative, Talon Voice alternative, best dictation software 2026, voice typing app comparison, [engine] Deepgram vs Whisper vs local.

**Pillar C — Voice for developers & power use (our unique angle).** Hub: a new `/voice-coding` style page (or the strongest blog post).
Cluster: dictate to Claude Code / Cursor / VS Code, coding by voice, voice typing for programmers, reduce RSI, prompt engineering by voice.

Plus **accessibility / inclusion** (RSI, disability, non-native English) which earns links + goodwill and is genuinely on-brand.

The blog batch (this overnight build) seeds 16 posts across these clusters with FAQ + Article + Breadcrumb structured data and internal links up to the hubs.

## 3. Content engine

- **Blog:** `/blog` index + ~16 articles (shipped this batch), each with a direct-answer intro (for AI), comparison tables, FAQ, internal links, and a download CTA.
- **Cadence going forward:** 1-2 posts/week. Refresh the top performers quarterly (Google rewards freshness; "Updated 2026" in the meta line).
- **Expansion ideas (next batches):** more `/vs/<competitor>` pages (Dragon, Talon, Voice Access, Otter, Superwhisper), more head-term landers (`/free-voice-typing`, `/speech-to-text-windows`, `/offline-dictation`), and per-use-case pages (writers, lawyers, students, accessibility).
- **Programmatic angle (later):** "voice typing in <app>" pages (Word, Outlook, Gmail, Slack, Notion, VS Code, Cursor) since Pipevoice's pitch is "any app". Only do this with genuinely distinct, useful content per page (thin programmatic pages get penalised).

## 4. Technical SEO (state)

Shipped in this build:
- ✅ `sitemap.xml` regenerated with all pages + every blog URL (priorities + lastmod).
- ✅ `robots.txt` allows all, points at sitemap, disallows `/admin`.
- ✅ Per-page **canonical**, **meta description**, **OG + Twitter** tags with the social image.
- ✅ **Structured data**: `Article` + `FAQPage` + `BreadcrumbList` on every post; `Blog` on the index; `SoftwareApplication` should be added to the homepage (see TODO).
- ✅ `llms.txt` at the root (an AI-crawler-friendly summary + link list).
- ✅ Mobile-responsive, fast (static HTML, system + Geist fonts, no JS frameworks), HTTPS, clean URLs.

TODO (quick, low-risk; some I can do, some need you):
- [ ] Add `SoftwareApplication` + `Organization` JSON-LD to the homepage (`index.html`) with `aggregateRating` once we have real reviews (don't fake it).
- [ ] Add a visible **Blog** link to the main site nav (currently the marketing nav is Why/Features/Stack/Setup) so crawlers + users find it. (I added Blog to the blog/docs nav; the marketing homepage nav still needs it.)
- [ ] **Google Search Console** + **Bing Webmaster Tools**: verify the domain, submit the sitemap (your action, §7).
- [ ] Decide brand casing: the logo says **PipeVoice**, the site copy says **Pipevoice**. Pick one for consistency (helps brand SERP). I recommend matching the logo: **PipeVoice**.

## 5. GEO (getting into AI answers)

AI engines (ChatGPT, Perplexity, Google AI Overviews, Claude) cite sources that are **clearly structured, factual, and answer the question directly**. What we're doing for that:
- Every article **opens with a 1-2 sentence direct answer** (quotable).
- **Comparison tables** and **explicit lists** ("the 5 best free…") that AI loves to extract.
- **FAQ schema** so engines can lift Q&A pairs.
- **`llms.txt`** summarising the product + linking the guides.
- Consistent, unhedged factual claims ("Pipevoice is free and open source", "runs fully offline with Local Whisper + Ollama").

Beyond on-site: AI engines lean heavily on **Reddit, GitHub, and review sites**. So the backlink/community work in §6 doubles as GEO work, getting Pipevoice mentioned on the sources AI reads. A well-starred GitHub repo with a strong README is itself a top AI citation source; keep the README sharp.

## 6. Backlinks (prepared, you fire the outward ones)

Tiered by effort/risk. I've drafted the copy (see `MARKETING_PLAN.md` + `DIRECTORY_KIT.md`); I did **not** auto-submit anything that touches your accounts/reputation.

**Tier 1 — directories & launch sites (do these first, biggest authority boost).** Use your **SignalEngine DirBot** for the ~100 directories. `DIRECTORY_KIT.md` has the exact copy for every field. High-value manual ones: Product Hunt, AlternativeTo, Slant, SaaSHub, GitHub topics/awesome-lists, Microsoft Store (once signed), tools.

**Tier 2 — community (high-trust, needs a real account + care).** Reddit (r/windows, r/software, r/productivity, r/accessibility, r/programming for the dev angle, r/dictation), Hacker News Show HN, dev.to / Hashnode cross-posts of the best blog articles, relevant Discord/Slack communities. **Caveat (from prior notes):** HN Show HN is gated for new accounts and Reddit is allergic to self-promo, so these must be genuine, value-first, and posted from an aged account. Drafts are ready; you post.

**Tier 3 — earned/outreach.** "Free alternative to X" roundups, accessibility blogs, indie-hacker newsletters, YouTube creators who cover dictation/RSI tools. Outreach templates in `MARKETING_PLAN.md`.

**Built-in flywheel:** every blog post is itself link-bait for the comparison/"free alternative" searches, and open-source repos attract organic links.

## 7. What you (James) need to do

1. **Google Search Console** (search.google.com/search-console): add `pipevoice.app`, verify via DNS TXT (Cloudflare) or the HTML-tag method, submit `https://pipevoice.app/sitemap.xml`. Same for **Bing Webmaster Tools** (covers ChatGPT/Copilot too).
2. **Analytics:** confirm the existing first-party tracking still fires, or add Plausible/Umami. (We deliberately avoid heavy pixels.)
3. **DirBot:** run the ~100-directory submission using `DIRECTORY_KIT.md`. This is the single biggest week-1 lever.
4. **Code signing:** finish the Microsoft/Azure signing so the download loses the SmartScreen warning, that conversion + trust win compounds everything else.
5. **Decide brand casing** (PipeVoice vs Pipevoice) so I can standardise.
6. **Approve the community/launch drafts** in `MARKETING_PLAN.md` and post from your accounts when ready (Product Hunt timing matters, pick a Tue-Thu).
7. Optional: get 5-10 real users to ★ the GitHub repo and leave honest reviews on AlternativeTo, big for both authority and AI citations.

## 8. 30 / 60 / 90 day roadmap

**Days 0-30:** ship blog (done), submit sitemaps, run DirBot directories, Product Hunt + one strong Reddit/HN value post, get the repo starred. Target: indexed + 30 referring domains.
**Days 30-60:** second content batch (more /vs pages + per-app pages), refresh weak posts, start light outreach to "free alternative" roundups, add SoftwareApplication schema + first real reviews. Target: first organic rankings on long-tail, first AI citations.
**Days 60-90:** double down on whatever cluster is ranking, build the developer/voice-coding angle (it's the most defensible), guest posts / newsletter mentions. Target: top-10 for a few long-tail terms, steady organic downloads.

The single highest-leverage things: **(1) finish code signing, (2) run DirBot, (3) keep shipping honest, useful content.** Everything else compounds off those.
