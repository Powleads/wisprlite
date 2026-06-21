"""Assemble Pipevoice blog pages from the SEO workflow output.

Reads /tmp/articles.json  (= {plan:{overview,pillars,articles:[...]}, articles:[{slug,title,h1,dek,
metaDescription,keyword,bodyHtml,faqs,readingMinutes}, ...]}) and writes:
  wisprlitevercel/blog/<slug>.html   (one full page per article, with Article+FAQ+Breadcrumb JSON-LD)
  wisprlitevercel/blog/index.html    (the blog index)
  wisprlitevercel/sitemap.xml         (regenerated: all pages + blog)
  wisprlitevercel/llms.txt            (AI-crawler summary)

Run:  python marketing/build_blog.py
"""
from __future__ import annotations
import html
import json
import os
import re

# Writers sometimes link to article slugs that did not make the final batch.
# Map those to the closest real article so no internal link 404s (and the link
# equity still flows). Truly unknown /blog/ links get unwrapped to plain text.
LINK_MAP = {
    "deepgram-vs-whisper-vs-openai-dictation": "speech-to-text-windows",
    "dictation-accuracy-tips": "speech-to-text-windows",
    "per-app-dictation-profiles": "voice-coding-windows",
    "voice-commands-dictation-windows": "how-to-dictate-on-windows",
    "voice-typing-accessibility-windows": "voice-typing-for-rsi",
    "win-h-voice-typing-not-working": "how-to-dictate-on-windows",
}


def fix_links(body, valid):
    def repl(m):
        whole = m.group(0)
        slug = m.group(1).split("#")[0].split("?")[0].rstrip("/")
        if slug in valid:
            return whole
        if slug in LINK_MAP:
            return re.sub(r'href="/blog/[^"]+"', 'href="/blog/%s"' % LINK_MAP[slug], whole, count=1)
        return m.group(2)  # unwrap: keep the anchor text, drop the dead link
    return re.sub(r'<a\s+href="/blog/([^"]+?)"[^>]*>(.*?)</a>', repl, body, flags=re.S)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "wisprlitevercel")
BLOG = os.path.join(WEB, "blog")
SITE = "https://pipevoice.app"
DL = "https://github.com/Powleads/PipeVoice/releases/latest/download/Pipevoice-Setup.exe"
PUBLISHED = "2026-06-22"  # overnight batch

STATIC_PAGES = [
    ("/", "1.0"),
    ("/windows-voice-typing", "0.9"),
    ("/vs/wispr-flow", "0.9"),
    ("/docs", "0.7"),
    ("/blog", "0.8"),
    ("/privacy", "0.3"),
]

CSS = """
:root{
  --canvas:#13151d; --deep:#0f1117; --card:#1b1e29;
  --border:rgba(53,90,102,.45); --border-soft:rgba(120,130,150,.16);
  --accent:#e06c75; --accent-soft:rgba(224,108,117,.12); --accent-line:rgba(224,108,117,.5);
  --good:#98c379; --warn:#e5c07b;
  --text:#e6e8eb; --muted:#9aa1ad; --r:10px;
  --mono:"Geist Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{background:var(--canvas);color:var(--text);
  font-family:"Geist",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;line-height:1.7;-webkit-font-smoothing:antialiased}
a{color:var(--accent);text-decoration:none} a:hover{text-decoration:underline}
.wrap{max-width:760px;margin:0 auto;padding:0 24px}
nav{display:flex;align-items:center;justify-content:space-between;padding:20px 0;border-bottom:1px solid var(--border-soft)}
.logo{display:flex;align-items:center;gap:10px}
.nav-links{display:flex;gap:22px;color:var(--muted);font-size:14.5px;flex-wrap:wrap}
.nav-links a{color:var(--muted)} .nav-links a:hover{color:var(--text);text-decoration:none}
.crumb{font-family:var(--mono);font-size:12.5px;color:var(--muted);margin:30px 0 0}
.crumb a{color:var(--muted)} .crumb a:hover{color:var(--accent)}
header.h{padding:14px 0 10px}
h1{font-size:clamp(28px,4.4vw,40px);letter-spacing:-.02em;font-weight:800;line-height:1.15}
.dek{color:var(--muted);margin-top:12px;font-size:17px;line-height:1.6}
.meta{color:var(--muted);font-family:var(--mono);font-size:12.5px;margin-top:14px;display:flex;gap:14px;flex-wrap:wrap}
article{padding:8px 0 10px}
article h2{font-size:25px;margin:40px 0 8px;letter-spacing:-.01em;scroll-margin-top:20px;font-weight:700}
article h3{font-size:18px;margin:26px 0 4px;font-weight:600}
article p{color:var(--text);opacity:.92;margin:12px 0;font-size:16.5px}
article ul,article ol{color:var(--text);opacity:.92;margin:12px 0 12px 24px} article li{margin:7px 0}
article a{color:var(--accent)} article strong{color:var(--text);opacity:1}
blockquote{border-left:3px solid var(--accent-line);background:var(--accent-soft);
  margin:18px 0;padding:12px 18px;border-radius:0 var(--r) var(--r) 0;color:var(--text)}
code,kbd{font-family:var(--mono);font-size:13.5px;background:var(--deep);border:1px solid var(--border-soft);
  border-radius:6px;padding:2px 7px;color:var(--text)}
kbd{box-shadow:0 1px 0 rgba(0,0,0,.4)}
table{width:100%;border-collapse:collapse;margin:20px 0;font-size:14.5px;display:block;overflow-x:auto}
th,td{text-align:left;padding:11px 14px;border-bottom:1px solid var(--border-soft);vertical-align:top}
th{color:var(--text);font-weight:600;white-space:nowrap;background:rgba(255,255,255,.02)}
td{color:var(--text);opacity:.9}
.note{background:var(--accent-soft);border:1px solid var(--accent-line);padding:14px 18px;border-radius:var(--r);margin:18px 0}
.note b{color:var(--text)}
.cta{background:var(--card);border:1px solid var(--border);border-radius:14px;padding:26px 24px;margin:36px 0;text-align:center}
.cta h3{font-size:21px;font-weight:700;margin-bottom:6px}
.cta p{color:var(--muted);font-size:14.5px;margin-bottom:16px}
.btn{display:inline-flex;align-items:center;gap:8px;background:var(--accent);color:#1a0c0d;font-weight:700;
  border-radius:var(--r);padding:13px 22px}
.btn:hover{filter:brightness(1.06);text-decoration:none}
.fine{color:var(--muted);font-family:var(--mono);font-size:12px;margin-top:12px}
.faq{margin:36px 0 0}
.faq h2{margin-bottom:6px}
details{border:1px solid var(--border-soft);border-radius:var(--r);padding:2px 18px;margin-bottom:10px;background:var(--card)}
summary{cursor:pointer;padding:15px 0;font-weight:600;list-style:none;font-size:16px}
summary::-webkit-details-marker{display:none}
summary::after{content:"+";float:right;color:var(--muted);font-family:var(--mono)}
details[open] summary::after{content:"\\2013"}
details p{color:var(--muted);padding:0 0 16px;font-size:15px}
.related{margin:42px 0 0;border-top:1px solid var(--border-soft);padding-top:26px}
.related h2{font-size:18px;margin-bottom:12px}
.related a{display:block;padding:10px 0;color:var(--text);border-bottom:1px solid var(--border-soft);font-size:15.5px}
.related a:hover{color:var(--accent);text-decoration:none}
.related a span{color:var(--muted);font-size:13px;display:block;margin-top:2px}
footer{border-top:1px solid var(--border-soft);margin-top:54px;padding:28px 0 44px;color:var(--muted);font-size:13.5px;font-family:var(--mono);
  display:flex;justify-content:space-between;flex-wrap:wrap;gap:12px}
footer a{color:var(--muted)} footer a:hover{color:var(--accent)}
.bloglist{margin:30px 0 0}
.bloglist .card{display:block;background:var(--card);border:1px solid var(--border-soft);border-radius:14px;padding:22px 24px;margin-bottom:14px;transition:.15s}
.bloglist .card:hover{border-color:var(--accent-line);transform:translateY(-2px);text-decoration:none}
.bloglist .tag{font-family:var(--mono);font-size:11px;letter-spacing:.05em;text-transform:uppercase;color:var(--accent)}
.bloglist h2{font-size:19px;font-weight:700;color:var(--text);margin:6px 0 4px}
.bloglist p{color:var(--muted);font-size:14.5px}
@media(max-width:640px){.nav-links{gap:14px;font-size:13px}}
"""

NAV = (
    '  <nav>\n'
    '    <div class="logo"><a href="/"><img src="/pipevoice-lockup.png" alt="Pipevoice" '
    'style="height:30px;width:auto;display:block" /></a></div>\n'
    '    <div class="nav-links">\n'
    '      <a href="/">Home</a>\n'
    '      <a href="/blog">Blog</a>\n'
    '      <a href="/windows-voice-typing">Windows voice typing</a>\n'
    '      <a href="/docs">Docs</a>\n'
    '      <a href="https://github.com/Powleads/PipeVoice">GitHub ↗</a>\n'
    '    </div>\n'
    '  </nav>\n'
)

FOOTER = (
    '  <footer>\n'
    '    <div>Pipevoice · free, private voice typing for Windows.</div>\n'
    '    <div><a href="/">Home</a> · <a href="/blog">Blog</a> · <a href="/privacy">Privacy</a> · '
    '<a href="https://github.com/Powleads/PipeVoice">GitHub</a></div>\n'
    '  </footer>\n'
)


def esc(s):
    return html.escape(s or "", quote=True)


def page_head(title, desc, canonical, jsonld):
    blocks = "\n".join(
        '<script type="application/ld+json">' + json.dumps(o, ensure_ascii=False) + "</script>" for o in jsonld
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}" />
<link rel="canonical" href="{canonical}" />
<meta name="robots" content="index, follow, max-image-preview:large" />
<meta property="og:type" content="article" />
<meta property="og:title" content="{esc(title)}" />
<meta property="og:description" content="{esc(desc)}" />
<meta property="og:url" content="{canonical}" />
<meta property="og:image" content="{SITE}/og-image.png" />
<meta property="og:image:width" content="1200" />
<meta property="og:image:height" content="630" />
<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content="{esc(title)}" />
<meta name="twitter:description" content="{esc(desc)}" />
<meta name="twitter:image" content="{SITE}/og-image.png" />
<link rel="icon" type="image/png" href="/favicon.png" />
<link rel="apple-touch-icon" href="/apple-touch-icon.png" />
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700;800&family=Geist+Mono:wght@400;500&display=swap" rel="stylesheet" />
{blocks}
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
{NAV}"""


def faq_html(faqs):
    if not faqs:
        return ""
    rows = "\n".join(
        f"      <details><summary>{esc(f['q'])}</summary><p>{esc(f['a'])}</p></details>" for f in faqs
    )
    return f'  <section class="faq">\n    <h2>FAQ</h2>\n{rows}\n  </section>\n'


def cta_html():
    return (
        '  <div class="cta">\n'
        '    <h3>Try Pipevoice free</h3>\n'
        '    <p>Push-to-talk voice typing for Windows. Free, open source, works offline. No account.</p>\n'
        f'    <a class="btn" href="{DL}">↓ Download for Windows</a>\n'
        '    <p class="fine">free forever · open source · Windows 10 &amp; 11</p>\n'
        '  </div>\n'
    )


def related_html(art, by_slug):
    links = []
    for s in (art.get("internalLinks") or [])[:4]:
        o = by_slug.get(s)
        if o and o["slug"] != art["slug"]:
            links.append(
                f'      <a href="/blog/{o["slug"]}">{esc(o["title"])}<span>{esc(o.get("dek",""))}</span></a>'
            )
    if not links:
        return ""
    return '  <section class="related">\n    <h2>Keep reading</h2>\n' + "\n".join(links) + "\n  </section>\n"


def build_article(art, by_slug):
    slug = art["slug"]
    canonical = f"{SITE}/blog/{slug}"
    title_tag = art["title"] if "pipevoice" in art["title"].lower() else f'{art["title"]} | Pipevoice'
    faqs = art.get("faqs") or []
    article_ld = {
        "@context": "https://schema.org", "@type": "Article",
        "headline": art["h1"][:110], "description": art["metaDescription"],
        "image": f"{SITE}/og-image.png", "datePublished": PUBLISHED, "dateModified": PUBLISHED,
        "author": {"@type": "Organization", "name": "Pipevoice", "url": SITE},
        "publisher": {"@type": "Organization", "name": "Pipevoice", "url": SITE,
                      "logo": {"@type": "ImageObject", "url": f"{SITE}/apple-touch-icon.png"}},
        "mainEntityOfPage": {"@type": "WebPage", "@id": canonical},
        "about": art.get("keyword", "voice typing for Windows"),
    }
    breadcrumb_ld = {
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE + "/"},
            {"@type": "ListItem", "position": 2, "name": "Blog", "item": SITE + "/blog"},
            {"@type": "ListItem", "position": 3, "name": art["title"], "item": canonical},
        ],
    }
    jsonld = [article_ld, breadcrumb_ld]
    if faqs:
        jsonld.append({
            "@context": "https://schema.org", "@type": "FAQPage",
            "mainEntity": [
                {"@type": "Question", "name": f["q"],
                 "acceptedAnswer": {"@type": "Answer", "text": f["a"]}} for f in faqs
            ],
        })
    mins = art.get("readingMinutes") or max(3, len(art.get("bodyHtml", "")) // 1400)
    head = page_head(title_tag, art["metaDescription"], canonical, jsonld)
    body = (
        '  <p class="crumb"><a href="/">Home</a> / <a href="/blog">Blog</a> / '
        f'{esc(art["title"])}</p>\n'
        '  <header class="h">\n'
        f'    <h1>{esc(art["h1"])}</h1>\n'
        f'    <p class="dek">{esc(art["dek"])}</p>\n'
        f'    <div class="meta"><span>{int(mins)} min read</span><span>Updated Jun 2026</span>'
        '<span>Free · Windows</span></div>\n'
        '  </header>\n'
        '  <article>\n' + fix_links(art["bodyHtml"], set(by_slug.keys())) + "\n  </article>\n"
        + cta_html()
        + faq_html(faqs)
        + related_html(art, by_slug)
    )
    return head + body + FOOTER + "</div>\n</body>\n</html>\n"


def build_index(articles, overview):
    canonical = f"{SITE}/blog"
    desc = "Guides, comparisons and how-tos for voice typing and dictation on Windows: free tools, offline speech-to-text, coding by voice, and more from Pipevoice."
    ld = [{
        "@context": "https://schema.org", "@type": "Blog", "@id": canonical,
        "name": "Pipevoice Blog", "description": desc, "url": canonical,
        "publisher": {"@type": "Organization", "name": "Pipevoice", "url": SITE},
        "blogPost": [{"@type": "BlogPosting", "headline": a["title"],
                      "url": f"{SITE}/blog/{a['slug']}", "datePublished": PUBLISHED} for a in articles],
    }, {
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE + "/"},
            {"@type": "ListItem", "position": 2, "name": "Blog", "item": canonical},
        ],
    }]
    head = page_head("Pipevoice Blog: voice typing & dictation for Windows", desc, canonical, ld)
    cards = []
    for a in articles:
        cards.append(
            f'    <a class="card" href="/blog/{a["slug"]}">\n'
            f'      <div class="tag">{esc(a.get("keyword",""))}</div>\n'
            f'      <h2>{esc(a["title"])}</h2>\n'
            f'      <p>{esc(a["dek"])}</p>\n'
            '    </a>\n'
        )
    body = (
        '  <p class="crumb"><a href="/">Home</a> / Blog</p>\n'
        '  <header class="h">\n    <h1>Pipevoice blog</h1>\n'
        '    <p class="dek">Guides, comparisons and how-tos for faster, more private voice typing on Windows: '
        'free tools, offline speech-to-text, dictating into your editor and terminal, and getting the most out of Pipevoice.</p>\n'
        '  </header>\n'
        '  <div class="bloglist">\n' + "".join(cards) + "  </div>\n"
        + cta_html()
    )
    return head + body + FOOTER + "</div>\n</body>\n</html>\n"


def build_sitemap(slugs):
    rows = []
    for loc, pr in STATIC_PAGES:
        rows.append(f"  <url><loc>{SITE}{loc}</loc><lastmod>{PUBLISHED}</lastmod><priority>{pr}</priority></url>")
    for s in slugs:
        rows.append(f"  <url><loc>{SITE}/blog/{s}</loc><lastmod>{PUBLISHED}</lastmod><priority>0.7</priority></url>")
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + "\n".join(rows) + "\n</urlset>\n")


def build_llms(articles):
    lines = [
        "# Pipevoice",
        "",
        "> Pipevoice is free, open-source, push-to-talk voice typing for Windows 10 and 11. Hold a hotkey, speak, release, and your words are typed as real keystrokes into any focused app (terminal, editor, browser, chat). It is the free, Windows-native, privacy-first alternative to paid Mac-first dictation apps.",
        "",
        "Key facts:",
        "- Free forever and open source (github.com/Powleads/PipeVoice). No account, no telemetry.",
        "- Three transcription engines: Deepgram (fastest, streaming), OpenAI Whisper (most accurate), Local Whisper (fully offline, free, no key).",
        "- Optional AI cleanup via OpenAI, free Google Gemini, free OpenRouter, or local Ollama. A Local Whisper + Ollama setup is 100% offline.",
        "- Types into ANY Windows app, including terminals running Claude Code, Cursor, and VS Code.",
        "- Windows only. Download: " + DL,
        "",
        "## Guides",
    ]
    for a in articles:
        lines.append(f"- [{a['title']}]({SITE}/blog/{a['slug']}): {a['metaDescription']}")
    lines += ["", "## Pages",
              f"- [Windows voice typing]({SITE}/windows-voice-typing)",
              f"- [Pipevoice vs Wispr Flow]({SITE}/vs/wispr-flow)",
              f"- [Docs / quickstart]({SITE}/docs)"]
    return "\n".join(lines) + "\n"


def main():
    data = json.load(open("/tmp/articles.json", encoding="utf-8"))
    plan = data.get("plan", {})
    arts = data["articles"]
    # normalise: verify step returns full fields; carry internalLinks from the plan
    plan_by_slug = {p["slug"]: p for p in plan.get("articles", [])}
    for a in arts:
        a.setdefault("internalLinks", plan_by_slug.get(a["slug"], {}).get("internalLinks", []))
        a.setdefault("dek", "")
        a.setdefault("keyword", plan_by_slug.get(a["slug"], {}).get("primaryKeyword", ""))
    by_slug = {a["slug"]: a for a in arts}
    os.makedirs(BLOG, exist_ok=True)
    for a in arts:
        open(os.path.join(BLOG, a["slug"] + ".html"), "w", encoding="utf-8").write(build_article(a, by_slug))
    open(os.path.join(BLOG, "index.html"), "w", encoding="utf-8").write(build_index(arts, plan.get("overview", "")))
    open(os.path.join(WEB, "sitemap.xml"), "w", encoding="utf-8").write(build_sitemap([a["slug"] for a in arts]))
    open(os.path.join(WEB, "llms.txt"), "w", encoding="utf-8").write(build_llms(arts))
    print(f"wrote {len(arts)} articles + index + sitemap + llms.txt")
    for a in arts:
        print(" /blog/" + a["slug"])


if __name__ == "__main__":
    main()
