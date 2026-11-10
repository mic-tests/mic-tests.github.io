#!/usr/bin/env python3
"""
Import /seo-content-generator output (open-source-on-page-seo-optimizer repo,
output/mictest/<out-slug>/) into this repo's src/content/<slug>.json.

Usage:
    python3 utilities/seo_batch/import_seo_output.py            # all pages in PAGES
    python3 utilities/seo_batch/import_seo_output.py echo-test  # one page (site slug)
    python3 utilities/seo_batch/import_seo_output.py --dry-run

Per page it overwrites:
    meta_title, meta_description, h1   <- meta.json (title / meta_description / h1)
    content_blocks                     <- content.html, split at every <h2>; the text before the
                                          first <h2> becomes the opening lead-text block
    faq                                <- config.json faqs_json, only when the run wrote one
                                          (otherwise the existing faq is kept)
    json_ld                            <- WebPage name/description synced to the new title/description
Images: output/<out-slug>/images/*.svg -> src/content_images/<slug>/ (generate.py copies them
to public/images/<slug>/), and content.html's relative images/<file> src becomes /images/<slug>/<file>.

Never touched: slug, nav_page_id, meta_keywords, intro_html (hero line + its silo slot_a marker),
tool_card_html, script, extra_style, ads.

LaTeX in the generated content (\\( .. \\) and $$ .. $$) is converted to plain HTML text because this
site loads no math renderer.

Silo markers are not written here: generate_silo_rotation.py injects them on its first run using
the heading targets in its SLOT_TARGETS table (updated alongside this import).

Rebuild afterwards:  build_data.py -> generate.py -> generate_silo_rotation.py (see CLAUDE.md).
"""
import argparse
import html
import json
import os
import re
import shutil
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONTENT_DIR = os.path.join(REPO, "src", "content")
IMAGES_DIR = os.path.join(REPO, "src", "content_images")
OPTIMIZER_OUTPUT = os.path.join(os.path.dirname(REPO), "open-source-on-page-seo-optimizer", "output", "mictest")

# site slug -> optimizer output folder. audio-latency-test and the "mic test online" home-page run
# (output/mictest/index) are deliberately not imported.
PAGES = {
    "index": "index-mic-test",
    "tone-generator": "tone-generator",
    "hearing-test": "hearing-test",
    "headphone-test": "headphone-test",
    "stereo-test": "stereo-test",
    "bass-test": "bass-test",
    "speaker-volume-test": "speaker-volume-test",
    "sound-level-meter": "sound-level-meter",
    "mic-recorder": "mic-recorder",
    "voice-frequency-analyzer": "voice-frequency-analyzer",
    "show-speakers": "show-speakers",
    "background-noise-analyzer": "background-noise-analyzer",
    "echo-test": "echo-test",
    "show-mic": "show-mic",
}

SUB = str.maketrans("0123456789-", "₀₁₂₃₄₅₆₇₈₉₋")
GREEK = {"lambda": "λ", "Delta": "Δ", "times": "×", "approx": "≈", "cdot": "·", "pm": "±", "le": "≤", "ge": "≥",
         "mu": "µ", "pi": "π", "quad": "  ", "left": "", "right": "", "log": "log", "cos": "cos", "sin": "sin", "tan": "tan"}


def _braced(s, i):
    """s[i] == '{' -> (inner, index after matching '}')."""
    depth, j = 0, i
    while j < len(s):
        depth += s[j] == "{"
        depth -= s[j] == "}"
        if depth == 0:
            return s[i + 1:j], j + 1
        j += 1
    raise ValueError("unbalanced braces in %r" % s)


def tex_to_html(t):
    t = re.sub(r"\\text\{([^}]*)\}", r"\1", t)
    # \frac{a}{b} -> a / b (parenthesised when it is more than a single token)
    while r"\frac" in t:
        i = t.index(r"\frac")
        a, j = _braced(t, i + 5)
        b, k = _braced(t, j)
        wrap = lambda x: x if re.fullmatch(r"[\w.]+", x) else "(%s)" % x
        t = t[:i] + "%s / %s" % (wrap(a), wrap(b)) + t[k:]
    t = re.sub(r"\\(?:,|\s)", " ", t)
    t = re.sub(r"\\([A-Za-z]+)(?![A-Za-z_])", lambda m: GREEK.get(m.group(1), m.group(0)), t)
    t = re.sub(r"\\log_(?:\{(\w+)\}|(\w))", lambda m: "log" + (m.group(1) or m.group(2)).translate(SUB), t)
    t = re.sub(r"\^\{([^}]*)\}", r"<sup>\1</sup>", t)
    t = re.sub(r"\^(\w)", r"<sup>\1</sup>", t)
    t = re.sub(r"_\{([^}]*)\}", r"<sub>\1</sub>", t)
    t = t.replace("{", "").replace("}", "")
    if "\\" in t:
        sys.exit("error: unconverted LaTeX left in %r" % t)
    return re.sub(r"\s+", " ", t).strip()


def convert_math(s):
    s = re.sub(r"\$\$(.+?)\$\$", lambda m: "<em>%s</em>" % tex_to_html(m.group(1)), s, flags=re.S)
    s = re.sub(r"\\\((.+?)\\\)", lambda m: tex_to_html(m.group(1)), s, flags=re.S)
    return s


def split_blocks(content_html):
    parts = re.split(r"(?=<h2[ >])", content_html)
    blocks = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if not p.startswith("<h2"):  # opening text before the first <h2>
            p = re.sub(r"<p>", '<p class="lead-text">', p, count=1)
        blocks.append({"id": None, "html": p})
    return blocks


def update_json_ld(node, title, description):
    if isinstance(node, list):
        for n in node:
            update_json_ld(n, title, description)
    elif isinstance(node, dict):
        if node.get("@type") in ("WebPage", "SoftwareApplication", "WebApplication"):
            node["name"] = title
            if "description" in node:
                node["description"] = description
        for v in node.values():
            if isinstance(v, (dict, list)):
                update_json_ld(v, title, description)


def import_page(slug, dry_run):
    src = os.path.join(OPTIMIZER_OUTPUT, PAGES[slug])
    path = os.path.join(CONTENT_DIR, slug + ".json")
    with open(path, encoding="utf-8") as f:
        page = json.load(f)
    with open(os.path.join(src, "meta.json"), encoding="utf-8") as f:
        meta = json.load(f)
    with open(os.path.join(src, "content.html"), encoding="utf-8") as f:
        body = f.read()

    body = re.sub(r"<!--.*?-->", "", body, flags=re.S)          # phase-5b markers etc.
    body = re.sub(r'src="images/([^"]+)"', lambda m: 'src="/images/%s/%s"' % (slug, m.group(1)), body)
    body = convert_math(body)

    page["meta_title"] = meta["title"]
    page["meta_description"] = meta["meta_description"]
    page["h1"] = meta["h1"]
    page["content_blocks"] = split_blocks(body)
    update_json_ld(page.get("json_ld"), meta["title"], meta["meta_description"])

    n_faq = 0
    cfg = os.path.join(src, "config.json")
    if os.path.exists(cfg):
        with open(cfg, encoding="utf-8") as f:
            faqs = json.load(f).get("faqs_json") or []
        if faqs:
            page["faq"] = [{"q": q["question"], "a": html.escape(q["answer"], quote=False)} for q in faqs]
            n_faq = len(faqs)

    n_img = 0
    img_src = os.path.join(src, "images")
    if os.path.isdir(img_src):
        files = [x for x in os.listdir(img_src) if x.lower().endswith(".svg")]
        n_img = len(files)
        if not dry_run:
            dest = os.path.join(IMAGES_DIR, slug)
            shutil.rmtree(dest, ignore_errors=True)
            os.makedirs(dest)
            for name in files:
                with open(os.path.join(img_src, name), encoding="utf-8") as f:
                    svg = f.read()
                svg = re.sub(r"<dc:identifier>[^<]*</dc:identifier>",
                             "<dc:identifier>https://mictest.dev/images/%s/%s</dc:identifier>" % (slug, name), svg)
                with open(os.path.join(dest, name), "w", encoding="utf-8") as f:
                    f.write(svg)

    if not dry_run:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(page, f, indent=2, ensure_ascii=False)
            f.write("\n")
    print("%-26s %2d blocks, %d faq, %d image(s)%s" % (slug, len(page["content_blocks"]), n_faq, n_img,
                                                       "  [dry-run]" if dry_run else ""))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("slugs", nargs="*", help="site slugs to import (default: all in PAGES)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    for slug in args.slugs or PAGES:
        if slug not in PAGES:
            sys.exit("error: %s is not in PAGES" % slug)
        import_page(slug, args.dry_run)


if __name__ == "__main__":
    main()
