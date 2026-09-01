#!/usr/bin/env python3
"""Authors src/data/site.json + src/data/tools.json for mictest.dev's
JSON-driven build pipeline (modeled on the passwordhive/hexcalculator
pattern — see CLAUDE.md for the full writeup).

Every tool page is a single file: src/content/<slug>.json carries the
*entire* page — meta_title/meta_description/meta_keywords, h1/eyebrow/
intro_html, the hero nameplate, the tool card's own markup, the sidebar,
content_blocks, faq, and that tool's own fully self-contained JS. This
function just loads those files (in TOOL_SLUGS order) and writes them out
as data/tools.json for generate.py to render. Adding a new tool means
writing one new content/<slug>.json and adding its slug to TOOL_SLUGS below.

Info pages (about/contact/troubleshooting/sitemap) are a separate, simpler
content/pages.json — see build_pages().
"""
import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
CONTENT_DIR = os.path.join(BASE_DIR, "content")

SITE_NAME = "MicTest"
DOMAIN = "mictest.dev"
HOME_SLUG = "index"
ADSENSE_PUBLISHER_ID = "5426315045205785"
GA_MEASUREMENT_ID = "G-1WX3LQQQH3"

# Order here has no effect on the rail nav (that's static in template.html) —
# it only controls sitemap.xml ordering.
TOOL_SLUGS = [
    "index",
    "show-mic",
    "mic-recorder",
    "sound-level-meter",
    "voice-frequency-analyzer",
    "background-noise-analyzer",
    "echo-test",
    "audio-latency-test",
    "show-speakers",
    "tone-generator",
    "stereo-test",
    "bass-test",
    "speaker-volume-test",
    "headphone-test",
    "hearing-test",
]

INFO_SLUGS = ["troubleshooting", "about", "contact", "privacy", "sitemap"]


def load_tool(slug):
    """Reads content/<slug>.json — the tool's entire page in one file. If a
    future tool's file doesn't exist yet, this raises rather than inventing
    placeholder content — add the file first."""
    path = os.path.join(CONTENT_DIR, "%s.json" % slug)
    with open(path, encoding="utf-8") as f:
        tool = json.load(f)
    return tool


def build_tools():
    tools = []
    for slug in TOOL_SLUGS:
        path = os.path.join(CONTENT_DIR, "%s.json" % slug)
        if not os.path.exists(path):
            print("  ! content/%s.json not written yet, skipping" % slug)
            continue
        tools.append(load_tool(slug))
    return tools


def build_pages():
    pages = []
    for slug in INFO_SLUGS:
        path = os.path.join(CONTENT_DIR, "pages", "%s.json" % slug)
        if not os.path.exists(path):
            print("  ! content/pages/%s.json not written yet, skipping" % slug)
            continue
        with open(path, encoding="utf-8") as f:
            pages.append(json.load(f))
    return pages


def build_site():
    return {
        "site_name": SITE_NAME,
        "domain": DOMAIN,
        "home_slug": HOME_SLUG,
        "adsense_publisher_id": ADSENSE_PUBLISHER_ID,
        "ga_measurement_id": GA_MEASUREMENT_ID,
    }


def main():
    tools = build_tools()
    pages = build_pages()
    site = build_site()

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(os.path.join(DATA_DIR, "tools.json"), "w", encoding="utf-8") as f:
        json.dump(tools, f, indent=2, ensure_ascii=False)
        f.write("\n")
    with open(os.path.join(DATA_DIR, "pages.json"), "w", encoding="utf-8") as f:
        json.dump(pages, f, indent=2, ensure_ascii=False)
        f.write("\n")
    with open(os.path.join(DATA_DIR, "site.json"), "w", encoding="utf-8") as f:
        json.dump(site, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print("Wrote %d tools, %d info pages." % (len(tools), len(pages)))


if __name__ == "__main__":
    main()
