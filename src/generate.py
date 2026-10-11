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
import re
import shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(BASE_DIR)
DATA_DIR = os.path.join(BASE_DIR, "data")
STATIC_DIR = os.path.join(BASE_DIR, "static")
OUTPUT_DIR = os.path.join(REPO_ROOT, "public")

# AdSense is temporarily disabled site-wide while awaiting approval — see
# CLAUDE.md's "AdSense — temporarily disabled" note. Flip back to True (and
# uncomment the <head> snippet in src/template.html / src/template-page.html)
# once approved; no other code changes are needed to restore ad rendering.
# ads.txt is intentionally NOT gated by this — it stays generated regardless
# (see write_robots_and_sitemap below).
ADS_ENABLED = False

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


# ---------------------------------------------------------------------------
# Section names + Table of Contents (ported from screen-resolution-checker /
# webcam-test.github.io). Each content_blocks entry is already its own panel
# opening one <h2> section, so the existing .content-panel wrapper becomes
# that section (tag <section>, plus the classes block / block alt — existing
# classes kept, so the look is unchanged). The section id is built from its
# own visible <h2> text (lowercase, apostrophes dropped, other punctuation ->
# '-', max 60 chars, de-duplicated); the <h2> is <id>-heading and labels the
# section. Every <h3>/<h4> is named the same way. A block that already has an
# "id" in its JSON keeps it as the section id. The table of contents adds no
# <h2> or <p>, so the silo script's positional targets are unchanged.
# ---------------------------------------------------------------------------

H2_TAG_RE = re.compile(r"<h2\b([^>]*)>(.*?)</h2>", re.IGNORECASE | re.DOTALL)
ID_ATTR_RE = re.compile(r'\bid="([^"]+)"')
SUB_HEADING_RE = re.compile(r"<(h[34])\b([^>]*)>(.*?)</\1>", re.IGNORECASE | re.DOTALL)
RESERVED_SECTION_IDS = {"faq", "comments", "about-the-author", "tool", "main-content", "page-title", "table-of-contents"}
TOC_ICON = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
            'aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h7"/></svg>')


def section_slug(heading_html, taken):
    text = html.unescape(re.sub(r"<[^>]+>", "", heading_html)).lower().replace("&", " and ")
    text = text.replace("'", "").replace("\u2019", "")
    slug = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    if len(slug) > 60:
        slug = slug[:60].rsplit("-", 1)[0]
    slug = slug or "section"
    base, n = slug, 2
    while slug in taken:
        slug, n = "%s-%d" % (base, n), n + 1
    taken.add(slug)
    return slug


def name_sub_headings(chunk, taken):
    """Give every <h3>/<h4> an id from its own text (existing ids kept) and
    return the chunk plus a nested [(id, text, [...])] list (h4s under h3)."""
    out, pos, tree = [], 0, []
    for m in SUB_HEADING_RE.finditer(chunk):
        tag, attrs, inner = m.group(1).lower(), m.group(2), m.group(3)
        existing = ID_ATTR_RE.search(attrs)
        hid = existing.group(1) if existing else section_slug(inner, taken)
        out.append(chunk[pos:m.start()])
        out.append(m.group(0) if existing else '<%s id="%s"%s>%s</%s>' % (tag, hid, attrs, inner, tag))
        pos = m.end()
        node = (hid, inner, [])
        if tag == "h4" and tree:
            tree[-1][2].append(node)
        else:
            tree.append(node)
    out.append(chunk[pos:])
    return "".join(out), tree


def render_toc_list(nodes, top=True):
    items = "".join(
        '<li><a href="#%s">%s</a>%s</li>' % (nid, html.escape(html.unescape(re.sub(r"<[^>]+>", "", text)).strip()),
                                             render_toc_list(children, top=False) if children else "")
        for nid, text, children in nodes)
    return '<ol class="%s">%s</ol>' % ("toc-list" if top else "toc-sublist", items)


def render_toc(tree):
    """Table of contents card between the tool and the article: one numbered
    list, h3 (h4) nested under their h2, FAQ last. Only with 3+ sections."""
    if len(tree) < 3:
        return ""
    return ('      <section class="block toc-block"><nav class="toc-card" aria-labelledby="table-of-contents">'
            '<div class="toc-title">%s<span id="table-of-contents">Table of Contents</span></div>%s</nav></section>'
            % (TOC_ICON, render_toc_list(tree)))


def name_sections(blocks, taken):
    """Name every content block's section and headings. Returns
    [(block_html, section_id_or_None)] and the TOC tree."""
    named, tree = [], []
    for block in blocks:
        chunk = block["html"]
        m = H2_TAG_RE.search(chunk)
        sid = block.get("id")
        if sid:
            taken.add(sid)
        if m:
            h2_id = ID_ATTR_RE.search(m.group(1))
            if not sid:
                sid = h2_id.group(1) if h2_id else section_slug(m.group(2), taken)
            if not h2_id:
                chunk = chunk[:m.start()] + '<h2 id="%s-heading"%s>%s</h2>' % (sid, m.group(1), m.group(2)) + chunk[m.end():]
                h2_id_val = "%s-heading" % sid
            else:
                h2_id_val = h2_id.group(1)
            chunk, sub_tree = name_sub_headings(chunk, taken)
            tree.append((sid, m.group(2), sub_tree))
            named.append((chunk, sid, h2_id_val))
        else:
            named.append((chunk, sid, None))
    return named, tree


def render_content_blocks(named, start_index=0):
    """named: [(html, section_id, heading_id)]. Blocks with an <h2> become
    <section> elements labelled by their heading; the alternating block /
    block alt classes count every panel from start_index."""
    parts = []
    for i, (chunk, sid, hid) in enumerate(named):
        cls = "block alt" if (start_index + i) % 2 == 1 else "block"
        if hid:
            parts.append('      <section class="content-panel prose max-w-none %s" id="%s" aria-labelledby="%s">\n%s\n      </section>'
                         % (cls, sid, hid, chunk))
        else:
            id_attr = ' id="%s"' % sid if sid else ""
            parts.append('      <div class="content-panel prose max-w-none %s"%s>\n%s\n      </div>' % (cls, id_attr, chunk))
    return "\n\n".join(parts)


def render_faq_block(faq_heading, faq_items, block_id="faq", alt=False):
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
        '      <section class="content-panel prose max-w-none block%s" id="%s" aria-labelledby="%s-heading">\n'
        '        <h2 id="%s-heading">%s</h2>\n%s\n'
        '      </section>'
    ) % (" alt" if alt else "", block_id, block_id, block_id, html.escape(faq_heading), "\n".join(items))


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


def render_ga_snippet(site):
    """Google tag (gtag.js) — on every page (tool, info, 404), unlike ads
    which are per-page/per-slot opt-in via each page's own "ads" config."""
    ga_id = site["ga_measurement_id"]
    return (
        "  <!-- Google tag (gtag.js) -->\n"
        '  <script async src="https://www.googletagmanager.com/gtag/js?id=%s"></script>\n'
        "  <script>\n"
        "    window.dataLayer = window.dataLayer || [];\n"
        "    function gtag(){dataLayer.push(arguments);}\n"
        "    gtag('js', new Date());\n\n"
        "    gtag('config', '%s');\n"
        "  </script>"
        % (ga_id, ga_id)
    )


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
    # Ids already used on the page (template, tool card, intro, script) must not be reused.
    taken = set(RESERVED_SECTION_IDS) | set(ID_ATTR_RE.findall(
        template + tool["tool_card_html"] + tool["intro_html"] + tool["script"] + tool.get("extra_style", "")))
    named, toc_tree = name_sections(content_blocks, taken)
    if tool.get("faq"):
        toc_tree.append(("faq", tool.get("faq_heading", "Frequently Asked Questions"), []))
    footer_ad_slot = ads.get("footer")
    footer_ad_html = render_ad_panel_fixed(footer_ad_slot, adsense_client, 300, 250) if (ADS_ENABLED and footer_ad_slot) else ""
    main_sections_parts = [render_toc(toc_tree)]
    if footer_ad_html and len(named) >= 3:
        main_sections_parts += [
            render_content_blocks(named[:2]),
            footer_ad_html,
            render_content_blocks(named[2:], start_index=2),
        ]
    else:
        main_sections_parts += [render_content_blocks(named), footer_ad_html]
    faq_block = render_faq_block(tool.get("faq_heading", "Frequently Asked Questions"), tool.get("faq", []),
                                 alt=len(named) % 2 == 1)
    if faq_block:
        main_sections_parts.append(faq_block)
    main_sections = "\n\n".join(p for p in main_sections_parts if p)

    header_ad_slot = ads.get("header")
    header_ad_html = render_ad_panel_header(header_ad_slot, adsense_client) if (ADS_ENABLED and header_ad_slot) else ""

    mid_ad_slot = ads.get("mid")
    mid_ad_html = render_ad_panel_fixed(mid_ad_slot, adsense_client, 300, 250) if (ADS_ENABLED and mid_ad_slot) else ""

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
        "H1": html.escape(tool["h1"]),
        "H1_ATTR": html.escape(tool["h1"]),
        "INTRO_HTML": "          " + tool["intro_html"],
        "HEADER_AD_HTML": header_ad_html,
        "TOOL_CARD_HTML": tool["tool_card_html"],
        "PAGE_STYLE": tool.get("extra_style", ""),
        "MID_AD_HTML": mid_ad_html,
        "ADSENSE_CLIENT": adsense_client,
        "GA_SNIPPET": render_ga_snippet(site),
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
    taken = set(RESERVED_SECTION_IDS) | set(ID_ATTR_RE.findall(template_page + page.get("subtitle_html", "")))
    named, toc_tree = name_sections(content_blocks, taken)
    if page.get("faq"):
        toc_tree.append(("faq", page.get("faq_heading", "Frequently Asked Questions"), []))
    parts = [render_toc(toc_tree)]
    inline_ads = {a["after_block"]: a for a in ads.get("inline", [])} if ADS_ENABLED else {}
    if -1 in inline_ads:
        a = inline_ads[-1]
        parts.append(render_ad_panel(a["slot"], adsense_client, min_height=a.get("min_height")))
    for i, item in enumerate(named):
        parts.append(render_content_blocks([item], start_index=i))
        if i in inline_ads:
            a = inline_ads[i]
            parts.append(render_ad_panel(a["slot"], adsense_client, min_height=a.get("min_height")))

    ad_slot = ads.get("mid") if ADS_ENABLED else None
    if ad_slot:
        parts.append(render_ad_panel(ad_slot, adsense_client))
    faq_block = render_faq_block(page.get("faq_heading", "Frequently Asked Questions"), page.get("faq", []),
                                 alt=len(named) % 2 == 1)
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
        "H1": html.escape(page["h1"]),
        "SUBTITLE_HTML": "      " + page["subtitle_html"],
        "PAGE_CONTENT": page_content,
        "ADSENSE_CLIENT": adsense_client,
        "GA_SNIPPET": render_ga_snippet(site),
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
        "GA_SNIPPET": render_ga_snippet(site),
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
