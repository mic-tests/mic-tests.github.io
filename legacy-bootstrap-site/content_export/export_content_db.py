#!/usr/bin/env python3
"""
Export a JSON content database for all MicTest pages.

For each page, walks the main content region (inside
`<div class="container main-wrap">`) and captures every heading
(H2-H6) plus every FAQ/troubleshooting accordion panel
(`<details class="panel"><summary>...`) as a flat, ordered list of
{level, heading, content} blocks. Content is plain text (tags
stripped, entities decoded); paragraphs, list items, definition-list
pairs, and table rows are each flattened to one line.

Deliberately excluded, since none of them are backed by heading
markup on any page:
  - the <h1> and its lead/intro paragraph
  - the interactive tool area (controls, mic-select, buttons)
  - sidebar chrome: testimonials, the review-submission form, ads

Run:
  python3 utilities/content_export/export_content_db.py
Output:
  utilities/content_export/content-db.json
"""

import html as html_lib
import json
import os
import re
from html.parser import HTMLParser

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# (filename, url slug) - excludes 404.html (error page, no real content)
# and googlecb346f17d96186ee.html (empty verification file, must not be touched).
PAGES = [
    ("index.html", "/"),
    ("about.html", "/about"),
    ("contact.html", "/contact"),
    ("sitemap.html", "/sitemap"),
    ("troubleshooting.html", "/troubleshooting"),
    ("tone-generator.html", "/tone-generator"),
    ("headphone-test.html", "/headphone-test"),
    ("stereo-test.html", "/stereo-test"),
    ("bass-test.html", "/bass-test"),
    ("speaker-volume-test.html", "/speaker-volume-test"),
    ("show-speakers.html", "/show-speakers"),
    ("hearing-test.html", "/hearing-test"),
    ("mic-recorder.html", "/mic-recorder"),
    ("audio-latency-test.html", "/audio-latency-test"),
    ("echo-test.html", "/echo-test"),
    ("show-mic.html", "/show-mic"),
    ("sound-level-meter.html", "/sound-level-meter"),
    ("background-noise-analyzer.html", "/background-noise-analyzer"),
    ("voice-frequency-analyzer.html", "/voice-frequency-analyzer"),
]

HEADING_TAGS = {"h2", "h3", "h4", "h5", "h6"}
LINE_TAGS = {"p", "li", "dt", "dd", "tr", "aside"}
CELL_TAGS = {"td", "th"}
SKIP_TAGS = {"script", "style"}
SKIP_CLASSES = {"testimonial", "review-form"}  # sidebar chrome, not article content
SKIP_IDS = {"device-details"}  # live/dynamic detected-device readout, not authored content
RELATED_TOOLS_RE = re.compile(r"related\b.*\btools?\b", re.I)

WS_RE = re.compile(r"\s+")


class ContentExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.sections = []
        self.current = None
        self.mode = None            # None | "heading" | "line" | "cell"
        self.buf = []
        self.row_cells = []
        self.pending_term = None
        self.skip_tag_depth = 0     # inside <script>/<style>
        self.div_depth = 0
        self.in_scope = False
        self.scope_div_depth = None
        self.skip_regions = []      # stack of div_depth values for SKIP_CLASSES divs

    # ---------------------------------------------------------------
    def handle_starttag(self, tag, attrs):
        attrs_d = dict(attrs)

        if tag == "div":
            self.div_depth += 1
            classes = attrs_d.get("class", "").split()
            if not self.in_scope and "container" in classes and "main-wrap" in classes:
                self.in_scope = True
                self.scope_div_depth = self.div_depth
            elif self.in_scope and not self.skip_regions and (
                any(c in SKIP_CLASSES for c in classes) or attrs_d.get("id") in SKIP_IDS
            ):
                self.skip_regions.append(self.div_depth)
            return

        if not self.in_scope or self.skip_regions:
            return

        if tag in SKIP_TAGS:
            self.skip_tag_depth += 1
            return
        if self.skip_tag_depth:
            return

        if tag in HEADING_TAGS:
            self._start_marker(tag)
        elif tag == "summary":
            self._start_marker("panel")
        elif tag in LINE_TAGS:
            self.buf = []
            self.mode = "line"
        elif tag in CELL_TAGS:
            self.buf = []
            self.mode = "cell"

    def handle_endtag(self, tag):
        if tag == "div":
            if self.skip_regions and self.div_depth == self.skip_regions[-1]:
                self.skip_regions.pop()
            if self.in_scope and self.div_depth == self.scope_div_depth:
                self.in_scope = False
                self.scope_div_depth = None
            self.div_depth -= 1
            return

        if not self.in_scope or self.skip_regions:
            return

        if tag in SKIP_TAGS:
            self.skip_tag_depth = max(0, self.skip_tag_depth - 1)
            return
        if self.skip_tag_depth:
            return

        if tag in HEADING_TAGS or tag == "summary":
            self.current["heading"] = self._collapse(self.buf)
            self.mode, self.buf = None, []
        elif tag == "dt":
            self.pending_term = self._collapse(self.buf)
            self.mode, self.buf = None, []
        elif tag == "dd":
            text = self._collapse(self.buf)
            if self.pending_term:
                self._append(f"{self.pending_term}: {text}")
                self.pending_term = None
            else:
                self._append(text)
            self.mode, self.buf = None, []
        elif tag == "li":
            text = self._collapse(self.buf)
            if text:
                self._append(f"- {text}")
            self.mode, self.buf = None, []
        elif tag in ("p", "aside"):
            text = self._collapse(self.buf)
            if text:
                self._append(text)
            self.mode, self.buf = None, []
        elif tag in CELL_TAGS:
            self.row_cells.append(self._collapse(self.buf))
            self.mode, self.buf = None, []
        elif tag == "tr":
            if self.row_cells:
                self._append(" | ".join(self.row_cells))
            self.row_cells = []
            self.mode, self.buf = None, []

    def handle_data(self, data):
        if self.mode in ("heading", "line", "cell"):
            self.buf.append(data)

    def handle_comment(self, data):
        pass  # ignore SILO_START/SILO_END markers etc.

    # ---------------------------------------------------------------
    def _start_marker(self, level):
        self.current = {"level": level, "heading": "", "content": ""}
        self.sections.append(self.current)
        self.mode, self.buf = "heading", []

    def _collapse(self, parts):
        text = html_lib.unescape("".join(parts))
        return WS_RE.sub(" ", text).strip()

    def _append(self, line):
        if self.current is None:
            return  # content before the first heading - tool area / intro, discarded
        self.current["content"] = (self.current["content"] + "\n" + line) if self.current["content"] else line


def strip_related_tools(sections):
    """Drop 'Related ... Tools' h2 sections and their h3 sub-cards (nav chrome,
    not article content - same convention CLAUDE.md applies to sidebar cards)."""
    out = []
    skipping = False
    for s in sections:
        if skipping:
            if s["level"] == "h2":
                skipping = False
            else:
                continue
        if s["level"] == "h2" and RELATED_TOOLS_RE.search(s["heading"]):
            skipping = True
            continue
        out.append(s)
    return out


def extract_page(path):
    with open(path, encoding="utf-8") as f:
        raw = f.read()
    parser = ContentExtractor()
    parser.feed(raw)
    parser.close()
    sections = [s for s in parser.sections if s["heading"] or s["content"]]
    return strip_related_tools(sections)


def main():
    db = {}
    for filename, slug in PAGES:
        path = os.path.join(REPO_ROOT, filename)
        if not os.path.exists(path):
            print(f"  ! missing {filename}, skipping")
            continue
        sections = extract_page(path)
        db[slug] = {"file": filename, "sections": sections}
        print(f"  {filename}: {len(sections)} sections")

    out_path = os.path.join(REPO_ROOT, "utilities", "content_export", "content-db.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
