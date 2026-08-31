#!/usr/bin/env python3
"""Renders src/data/{tools,pages,site}.json + src/template.html /
src/template-page.html into public/*.html. No minification, no critical-CSS
step (deliberately — see CLAUDE.md) — this is the simple core of the
passwordhive/hexcalculator pattern without their Node/Chrome toolchain.

Run, in this order (see CLAUDE.md's "Build order matters" for why):
  python3 src/build_data.py                                 # (re)write data/tools.json, pages.json, site.json
  python3 src/generate.py                                   # render public/
  python3 utilities/silo_linking/generate_silo_rotation.py  # patch this month's silo links into public/*.html — LAST

That third step is not optional. It patches the already-rendered
public/*.html files in place via comment markers and never touches
src/content/ — so skipping it, or running this script again afterward
without re-running it, silently reverts the current month's silo
rotation back to whatever's baked into each page's
src/content/<slug>.json.

Never hand-edit anything in public/ — edit src/content/<slug>.json (or
src/content/pages/<slug>.json for info pages) and rerun the full
sequence above.
"""
import html
import json
import os
import shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(BASE_DIR)
DATA_DIR = os.path.join(BASE_DIR, "data")
STATIC_DIR = os.path.join(BASE_DIR, "static")
OUTPUT_DIR = os.path.join(REPO_ROOT, "public")

# Binary/opaque assets that can't be derived from site.json — copied as-is
# from src/static/. CNAME and ads.txt are NOT here: they're fully generated
# from site.json below (see write_robots_and_sitemap) so the domain and
# AdSense publisher ID have one source of truth.
STATIC_FILES = [
    "favicon.ico", "icon.png", "icon.svg",
    "googlecb346f17d96186ee.html",
]


def apply_tokens(template, tokens):
    out = template
    for k, v in tokens.items():
        out = out.replace("{{%s}}" % k, v)
    return out


def render_json_ld(data):
    return '  <script type="application/ld+json">\n%s\n  </script>' % json.dumps(data, indent=2, ensure_ascii=False)


def render_ad_panel(slot_id, adsense_client, min_height=None):
    style_extra = ";min-height:%dpx;" % min_height if min_height else ""
    body_style = ' style="min-height:%dpx;"' % min_height if min_height else ""
    return (
        '          <div class="ad-panel">\n'
        '            <div class="ad-panel-hdr"><i class="bi bi-megaphone me-2"></i>Advertisement</div>\n'
        '            <div class="ad-panel-body"%s>\n'
        '              <ins class="adsbygoogle"\n'
        '                   style="display:block%s"\n'
        '                   data-ad-client="%s"\n'
        '                   data-ad-slot="%s"\n'
        '                   data-ad-format="auto"\n'
        '                   data-full-width-responsive="true"></ins>\n'
        '              <script>(adsbygoogle = window.adsbygoogle || []).push({});</script>\n'
        '            </div>\n'
        '          </div>'
    ) % (body_style, style_extra, adsense_client, slot_id)


def render_ad_panel_fixed(slot_id, adsense_client, width, height):
    """Fixed-size ad unit (passwordhive's render_adsense_slot() pattern) —
    the <ins> declares width/height directly and omits data-ad-format/
    data-full-width-responsive entirely (those are for responsive units
    only; mixing both is invalid per AdSense's own spec). The explicit
    size reserves its layout space immediately at paint, before AdSense's
    script has run, so this can't cause CLS the way the auto/responsive
    render_ad_panel() above can without an explicit min-height."""
    return (
        '          <div class="ad-panel">\n'
        '            <div class="ad-panel-hdr"><i class="bi bi-megaphone me-2"></i>Advertisement</div>\n'
        '            <div class="ad-panel-body">\n'
        '              <ins class="adsbygoogle"\n'
        '                   style="display:inline-block;width:%dpx;height:%dpx"\n'
        '                   data-ad-client="%s"\n'
        '                   data-ad-slot="%s"></ins>\n'
        '              <script>(adsbygoogle = window.adsbygoogle || []).push({});</script>\n'
        '            </div>\n'
        '          </div>'
    ) % (width, height, adsense_client, slot_id)


def render_ad_panel_header(slot_id, adsense_client):
    """Responsive leaderboard slot, passwordhive's render_adsense_header()
    pattern: 728x90 at >=768px, 300x100 below that, resized via inline JS
    (not data-ad-format="auto") since fixed sizing needs the exact pixel
    value known ahead of the AdSense push() call. .ad-panel-header's CSS
    (min-height per breakpoint, mirroring passwordhive's .ad-slot-header)
    reserves the container's space before this script runs, same as the
    fixed-size ads' inline width/height does immediately."""
    return (
        '          <div class="ad-panel ad-panel-header">\n'
        '            <div class="ad-panel-hdr"><i class="bi bi-megaphone me-2"></i>Advertisement</div>\n'
        '            <div class="ad-panel-body">\n'
        '              <ins class="adsbygoogle" id="adsense-header"\n'
        '                   data-ad-client="%s"\n'
        '                   data-ad-slot="%s"></ins>\n'
        '              <script>(function(){\n'
        '                var ins=document.getElementById("adsense-header");\n'
        '                if(window.innerWidth>=768){ins.style.display="inline-block";ins.style.width="728px";ins.style.height="90px";}\n'
        '                else{ins.style.display="inline-block";ins.style.width="300px";ins.style.height="100px";}\n'
        '                (adsbygoogle=window.adsbygoogle||[]).push({});\n'
        '              })();</script>\n'
        '            </div>\n'
        '          </div>'
    ) % (adsense_client, slot_id)


def render_content_blocks(blocks):
    parts = []
    for block in blocks:
        id_attr = ' id="%s"' % block["id"] if block.get("id") else ""
        parts.append('      <div class="content-panel prose max-w-none"%s>\n%s\n      </div>' % (id_attr, block["html"]))
    return "\n\n".join(parts)


def render_faq_block(faq_heading, faq_items, block_id="faq"):
    if not faq_items:
        return ""
    items = []
    for item in faq_items:
        items.append(
            '        <details class="panel" open>\n'
            '          <summary><strong>%s</strong></summary>\n'
            '          <p>%s</p>\n'
            '        </details>' % (html.escape(item["q"]), item["a"])
        )
    return (
        '      <div class="content-panel prose max-w-none" id="%s">\n'
        '        <h2>%s</h2>\n%s\n'
        '      </div>'
    ) % (block_id, html.escape(faq_heading), "\n".join(items))


def render_faq_jsonld(faq_items):
    if not faq_items:
        return ""
    entities = [
        {
            "@type": "Question",
            "name": item["q"],
            "acceptedAnswer": {"@type": "Answer", "text": html.unescape(_strip_tags(item["a"]))},
        }
        for item in faq_items
    ]
    data = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": entities}
    return '  <script type="application/ld+json">\n%s\n  </script>' % json.dumps(data, indent=2, ensure_ascii=False)


def _strip_tags(s):
    import re
    return re.sub(r"<[^>]+>", "", s)


def render_page(tool, site, template):
    canonical = "https://%s/" % site["domain"] if tool["slug"] == site["home_slug"] else "https://%s/%s" % (site["domain"], tool["slug"])
    ads = tool.get("ads", {})
    adsense_client = "ca-pub-%s" % site["adsense_publisher_id"]

    # The 3rd ad (ads.footer) sits right before the 3rd H2 section — each
    # content_blocks entry opens with its own H2, so "before the 3rd H2" is
    # "before content_blocks[2]" — falling back to its old end-of-content
    # position (before FAQ/Comments) for the (currently none) pages with
    # fewer than 3 content_blocks.
    content_blocks = tool.get("content_blocks", [])
    footer_ad_slot = ads.get("footer")
    footer_ad_html = render_ad_panel_fixed(footer_ad_slot, adsense_client, 300, 250) if footer_ad_slot else ""
    if footer_ad_html and len(content_blocks) >= 3:
        main_sections_parts = [
            render_content_blocks(content_blocks[:2]),
            footer_ad_html,
            render_content_blocks(content_blocks[2:]),
        ]
    else:
        main_sections_parts = [render_content_blocks(content_blocks), footer_ad_html]
    faq_block = render_faq_block(tool.get("faq_heading", "Frequently Asked Questions"), tool.get("faq", []))
    if faq_block:
        main_sections_parts.append(faq_block)
    main_sections = "\n\n".join(p for p in main_sections_parts if p)

    header_ad_slot = ads.get("header")
    header_ad_html = render_ad_panel_header(header_ad_slot, adsense_client) if header_ad_slot else ""

    mid_ad_slot = ads.get("mid")
    mid_ad_html = render_ad_panel_fixed(mid_ad_slot, adsense_client, 300, 250) if mid_ad_slot else ""

    json_ld_blocks = [render_json_ld(tool["json_ld"])]
    faq_jsonld = render_faq_jsonld(tool.get("faq", []))
    if faq_jsonld:
        json_ld_blocks.append(faq_jsonld)

    tokens = {
        "META_TITLE": html.escape(tool["meta_title"]),
        "META_DESCRIPTION": html.escape(tool["meta_description"]),
        "META_KEYWORDS": html.escape(tool["meta_keywords"]),
        "CANONICAL_URL": canonical,
        "JSON_LD": "\n\n".join(json_ld_blocks),
        "H1": tool["h1"],
        "H1_ATTR": html.escape(tool["h1"]),
        "INTRO_HTML": "          " + tool["intro_html"],
        "HEADER_AD_HTML": header_ad_html,
        "TOOL_CARD_HTML": tool["tool_card_html"],
        "PAGE_STYLE": tool.get("extra_style", ""),
        "MID_AD_HTML": mid_ad_html,
        "ADSENSE_CLIENT": adsense_client,
        "MAIN_SECTIONS": main_sections,
        "TOOL_SCRIPT": tool["script"],
    }
    return apply_tokens(template, tokens)


def render_info_page(page, site, template_page):
    canonical = "https://%s/%s" % (site["domain"], page["slug"])
    adsense_client = "ca-pub-%s" % site["adsense_publisher_id"]
    ads = page.get("ads", {})

    # Most info pages take a single ad, appended after all content blocks
    # (ads.mid). troubleshooting.html's legacy design had a genuine sidebar
    # with its own ad column that the single-column info-page template
    # doesn't have room for — its 3 ad units are instead interspersed
    # between content_blocks at their original relative positions via
    # ads.inline: [{"after_block": <0-indexed content_blocks index>,
    # "slot": "...", "min_height": <optional int>}, ...].
    content_blocks = page.get("content_blocks", [])
    parts = []
    inline_ads = {a["after_block"]: a for a in ads.get("inline", [])}
    if -1 in inline_ads:
        a = inline_ads[-1]
        parts.append(render_ad_panel(a["slot"], adsense_client, min_height=a.get("min_height")))
    for i, block in enumerate(content_blocks):
        parts.append(render_content_blocks([block]))
        if i in inline_ads:
            a = inline_ads[i]
            parts.append(render_ad_panel(a["slot"], adsense_client, min_height=a.get("min_height")))

    ad_slot = ads.get("mid")
    if ad_slot:
        parts.append(render_ad_panel(ad_slot, adsense_client))
    faq_block = render_faq_block(page.get("faq_heading", "Frequently Asked Questions"), page.get("faq", []))
    if faq_block:
        parts.append(faq_block)
    page_content = "\n\n".join(p for p in parts if p)

    json_ld_blocks = [render_json_ld(page["json_ld"])]
    faq_jsonld = render_faq_jsonld(page.get("faq", []))
    if faq_jsonld:
        json_ld_blocks.append(faq_jsonld)

    tokens = {
        "META_TITLE": html.escape(page["meta_title"]),
        "META_DESCRIPTION": html.escape(page["meta_description"]),
        "CANONICAL_URL": canonical,
        "JSON_LD": "\n\n".join(json_ld_blocks),
        "H1": page["h1"],
        "SUBTITLE_HTML": "      " + page["subtitle_html"],
        "PAGE_CONTENT": page_content,
        "ADSENSE_CLIENT": adsense_client,
    }
    return apply_tokens(template_page, tokens)


def render_404(site, template_page):
    domain = site["domain"]
    suggestions = [
        ("mic-recorder", "bi-record-circle", "Mic Recorder", "Record your voice online"),
        ("stereo-test", "bi-badge-hd", "Stereo Test", "Check left/right channels"),
        ("headphone-test", "bi-headphones", "Headphone Test", "Test your headphones"),
    ]
    cards = "\n".join(
        '          <a href="/%s" class="panel p-4 text-center" style="display:block">\n'
        '            <i class="bi %s" style="font-size:1.75rem;color:var(--amber)"></i>\n'
        '            <div class="mt-2 mb-1" style="font-weight:600;color:var(--ink)">%s</div>\n'
        '            <div class="text-muted">%s</div>\n'
        '          </a>' % (slug, icon, label, desc)
        for slug, icon, label, desc in suggestions
    )
    page_content = (
        '      <div class="content-panel" style="text-align:center">\n'
        '        <div class="mono" style="font-size:5rem;font-weight:700;color:var(--amber);line-height:1">404</div>\n'
        '        <p style="font-size:1.05rem;color:var(--ink-2)">The page you&#x27;re looking for doesn&#x27;t exist. It might have been moved, or you entered an incorrect URL.</p>\n'
        '        <div class="btn-toolbar" style="justify-content:center;margin:1.5rem 0 2rem">\n'
        '          <a href="/" class="btn btn-primary"><i class="bi bi-mic-fill me-2"></i>Test Microphone</a>\n'
        '          <a href="/troubleshooting" class="btn btn-outline"><i class="bi bi-question-circle me-2"></i>Troubleshooting</a>\n'
        '        </div>\n'
        '        <div class="grid sm:grid-cols-3 gap-3" style="text-align:left">\n'
        '%s\n'
        '        </div>\n'
        '      </div>'
    ) % cards

    tokens = {
        "META_TITLE": "Page Not Found - MicTest",
        "META_DESCRIPTION": "The page you&#x27;re looking for doesn&#x27;t exist. Return to MicTest to test your microphone and audio devices.",
        "CANONICAL_URL": "https://%s/404" % domain,
        "JSON_LD": "",
        "H1": "Page Not Found",
        "SUBTITLE_HTML": '<p style="color:var(--ink-2)">Let&#x27;s get you back to testing.</p>',
        "PAGE_CONTENT": page_content,
        "ADSENSE_CLIENT": "ca-pub-%s" % site["adsense_publisher_id"],
    }
    out = apply_tokens(template_page, tokens)
    out = out.replace(
        '<link rel="canonical" href="https://%s/404">' % domain,
        '<link rel="canonical" href="https://%s/404">\n  <meta name="robots" content="noindex, follow">' % domain,
    )
    return out


def write_robots_and_sitemap(site, tools, pages, out_dir):
    domain = site["domain"]
    with open(os.path.join(out_dir, "robots.txt"), "w", encoding="utf-8") as f:
        f.write("Sitemap: https://%s/sitemap.xml\n\nUser-agent: *\nDisallow:\n" % domain)

    urls = ["/"] + ["/%s" % t["slug"] for t in tools if t["slug"] != site["home_slug"]]
    urls += ["/%s" % p["slug"] for p in pages]
    entries = "\n\n  ".join(
        '<url><loc>https://%s%s</loc><lastmod>%s</lastmod><priority>%s</priority></url>' % (
            domain, u, site.get("lastmod", ""), "1.00" if u == "/" else "0.80"
        ) for u in urls
    )
    with open(os.path.join(out_dir, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n\n  %s\n\n</urlset>\n' % entries
        )

    # CNAME and ads.txt are one-liners fully derived from site.json — no
    # reason to hand-maintain a second copy of the domain / publisher ID.
    with open(os.path.join(out_dir, "CNAME"), "w", encoding="utf-8") as f:
        f.write("%s\n" % domain)
    with open(os.path.join(out_dir, "ads.txt"), "w", encoding="utf-8") as f:
        f.write("google.com, pub-%s, DIRECT, f08c47fec0942fa0\n" % site["adsense_publisher_id"])


def main():
    with open(os.path.join(DATA_DIR, "site.json"), encoding="utf-8") as f:
        site = json.load(f)
    with open(os.path.join(DATA_DIR, "tools.json"), encoding="utf-8") as f:
        tools = json.load(f)
    with open(os.path.join(DATA_DIR, "pages.json"), encoding="utf-8") as f:
        pages = json.load(f)
    with open(os.path.join(BASE_DIR, "template.html"), encoding="utf-8") as f:
        template = f.read()
    with open(os.path.join(BASE_DIR, "template-page.html"), encoding="utf-8") as f:
        template_page = f.read()

    site["lastmod"] = __import__("datetime").date.today().isoformat()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for tool in tools:
        out_html = render_page(tool, site, template)
        filename = "index.html" if tool["slug"] == site["home_slug"] else "%s.html" % tool["slug"]
        with open(os.path.join(OUTPUT_DIR, filename), "w", encoding="utf-8") as f:
            f.write(out_html)

    for page in pages:
        out_html = render_info_page(page, site, template_page)
        with open(os.path.join(OUTPUT_DIR, "%s.html" % page["slug"]), "w", encoding="utf-8") as f:
            f.write(out_html)

    with open(os.path.join(OUTPUT_DIR, "404.html"), "w", encoding="utf-8") as f:
        f.write(render_404(site, template_page))

    for name in STATIC_FILES:
        src = os.path.join(STATIC_DIR, name)
        if os.path.exists(src):
            shutil.copy(src, os.path.join(OUTPUT_DIR, name))
        else:
            print("  ! src/static/%s not found, skipping" % name)

    write_robots_and_sitemap(site, tools, pages, OUTPUT_DIR)

    print("Built %d tool pages + %d info pages into %s" % (len(tools), len(pages), OUTPUT_DIR))


if __name__ == "__main__":
    main()
