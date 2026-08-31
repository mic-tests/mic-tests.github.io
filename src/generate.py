#!/usr/bin/env python3
"""Renders src/data/{tools,pages,site}.json + src/template.html /
src/template-page.html into public/*.html. No minification, no critical-CSS
step (deliberately — see CLAUDE.md) — this is the simple core of the
passwordhive/hexcalculator pattern without their Node/Chrome toolchain.

Run:
  python3 src/build_data.py   # (re)write data/tools.json, pages.json, site.json
  python3 src/generate.py     # render public/

Never hand-edit anything in public/ — edit src/content/<slug>.json (or
src/content/pages/<slug>.json for info pages) and rerun both scripts.
"""
import html
import json
import os
import shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(BASE_DIR)
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(REPO_ROOT, "public")

STATIC_FILES = [
    "favicon.ico", "icon.png", "icon.svg", "CNAME", "ads.txt",
    "googlecb346f17d96186ee.html",
]


def apply_tokens(template, tokens):
    out = template
    for k, v in tokens.items():
        out = out.replace("{{%s}}" % k, v)
    return out


def render_json_ld(data):
    return '  <script type="application/ld+json">\n%s\n  </script>' % json.dumps(data, indent=2, ensure_ascii=False)


def render_nameplate(rows):
    """rows: list of [label, value, accent(bool)]."""
    parts = []
    for label, value, accent in rows:
        value_style = ' style="color:var(--amber)"' if accent else ""
        parts.append(
            '            <div class="flex items-center justify-between"><dt style="color:var(--ink-3)">%s</dt><dd%s>%s</dd></div>'
            % (html.escape(label), value_style, value)
        )
    return "\n".join(parts)


def render_ad_panel(slot_id, min_height=None):
    style_extra = ";min-height:%dpx;" % min_height if min_height else ""
    body_style = ' style="min-height:%dpx;"' % min_height if min_height else ""
    return (
        '          <div class="ad-panel">\n'
        '            <div class="ad-panel-hdr"><i class="bi bi-megaphone me-2"></i>Advertisement</div>\n'
        '            <div class="ad-panel-body"%s>\n'
        '              <ins class="adsbygoogle"\n'
        '                   style="display:block%s"\n'
        '                   data-ad-client="ca-pub-5426315045205785"\n'
        '                   data-ad-slot="%s"\n'
        '                   data-ad-format="auto"\n'
        '                   data-full-width-responsive="true"></ins>\n'
        '              <script>(adsbygoogle = window.adsbygoogle || []).push({});</script>\n'
        '            </div>\n'
        '          </div>'
    ) % (body_style, style_extra, slot_id)


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

    main_sections_parts = [render_content_blocks(tool.get("content_blocks", []))]
    footer_ad_slot = ads.get("footer")
    if footer_ad_slot:
        main_sections_parts.append(render_ad_panel(footer_ad_slot))
    faq_block = render_faq_block(tool.get("faq_heading", "Frequently Asked Questions"), tool.get("faq", []))
    if faq_block:
        main_sections_parts.append(faq_block)
    main_sections = "\n\n".join(p for p in main_sections_parts if p)

    sidebar_parts = [tool.get("sidebar_top_html", "")]
    sidebar_ad_slot = ads.get("sidebar")
    if sidebar_ad_slot:
        sidebar_parts.append(render_ad_panel(sidebar_ad_slot, min_height=360))
    sidebar_parts.append(tool.get("sidebar_bottom_html", ""))
    sidebar_html = "\n\n".join(p for p in sidebar_parts if p)

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
        "EYEBROW": tool["eyebrow"],
        "H1": tool["h1"],
        "INTRO_HTML": "          " + tool["intro_html"],
        "NAMEPLATE_HTML": render_nameplate(tool["nameplate"]),
        "TOOL_CARD_HTML": tool["tool_card_html"],
        "PAGE_STYLE": tool.get("extra_style", ""),
        "AD_SLOT_MID": ads.get("mid", ""),
        "MAIN_SECTIONS": main_sections,
        "SIDEBAR_HTML": sidebar_html,
        "TOOL_SCRIPT": tool["script"],
    }
    return apply_tokens(template, tokens)


def render_info_page(page, site, template_page):
    canonical = "https://%s/%s" % (site["domain"], page["slug"])

    parts = [render_content_blocks(page.get("content_blocks", []))]
    ad_slot = page.get("ads", {}).get("mid")
    if ad_slot:
        parts.append(render_ad_panel(ad_slot))
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
        "EYEBROW": page["eyebrow"],
        "H1": page["h1"],
        "SUBTITLE_HTML": "      " + page["subtitle_html"],
        "PAGE_CONTENT": page_content,
    }
    return apply_tokens(template_page, tokens)


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

    for name in STATIC_FILES:
        src = os.path.join(REPO_ROOT, name)
        if os.path.exists(src):
            shutil.copy(src, os.path.join(OUTPUT_DIR, name))

    write_robots_and_sitemap(site, tools, pages, OUTPUT_DIR)

    print("Built %d tool pages + %d info pages into %s" % (len(tools), len(pages), OUTPUT_DIR))


if __name__ == "__main__":
    main()
