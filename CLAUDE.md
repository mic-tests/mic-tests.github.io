# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**MicTest** is a static website hosted on GitHub Pages at https://mic-tests.github.io. It provides browser-based audio testing tools (microphone, speaker, headphone, hearing tests) using the Web Audio API.

## Deployment

This is a static site with no build step. Deploying means pushing to `main`:

```bash
git push origin main
```

GitHub Pages serves the site automatically from the `main` branch.

## Local Development

Serve locally with any HTTP server (file:// URLs may block microphone access due to browser security):

```bash
python3 -m http.server 8000
# or
npx serve .
```

There are no linters, test suites, or package managers configured.

## Architecture

### No Build Pipeline
All pages are self-contained HTML files with inline CSS/JS. There is no transpilation, bundling, or minification step — files are served as-is.

### Fully Inlined Pages
The navbar and footer are duplicated inline in every HTML page (no partials, no shared templates). When updating shared UI elements like navigation links or footer content, **every HTML file must be edited**. Use grep to find all instances before making changes.

### Per-Page Audio Logic
Each tool page is standalone — all its JavaScript lives inline in that page's `<script>` tag. The Web Audio API is the core technology: `getUserMedia` for mic input, `AnalyserNode` for frequency data, `OscillatorNode` for tone generation, `MediaRecorder` for recording.

### Shared Styles
- `css/common.css` — shared component styles (footer, cards, status indicators). Contains an explicit `strong, b { font-weight: 700; }` rule required to fix DM Sans bold rendering.
- `css/style.css` — HTML5 Boilerplate base reset (not project-specific)
- `css/design.css` — site-wide design tokens (typography, colour palette, spacing)
- Bootstrap 5.3.0-alpha1 and Bootstrap Icons 1.11.1 are loaded via CDN (jsdelivr)

**Font weight note:** DM Sans is loaded from Google Fonts with weight `700` explicitly in the URL. Without it, `<strong>` tags render at weight 400 because the browser has no 700 variant to fall back to. All pages must use:
```
DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,400
```

### SEO Structure
Each page should have:
- A canonical `<link>` tag using an extensionless URL (e.g. `https://mic-tests.github.io/tone-generator`)
- JSON-LD structured data (Schema.org `WebPage` or `SoftwareApplication`)
- Meta description and keywords
- Entry in `sitemap.xml`

## External Dependencies (CDN only)

| Dependency | Version | Purpose |
|---|---|---|
| Bootstrap | 5.3.0-alpha1 | UI framework |
| Bootstrap Icons | 1.11.1 | Icon set |
| Google AdSense | — | Monetization (pub ID: ca-pub-5426315045205785) |

## Key Files

- `sitemap.xml` — update `<lastmod>` dates when pages change
- `robots.txt` — SEO robots directives
- `ads.txt` — AdSense publisher configuration
- `googlecb346f17d96186ee.html` — Google Search Console verification (do not modify)
- `utilities/silo_linking/generate_silo_rotation.py` — monthly rotation script
- `.github/workflows/silo-rotation.yml` — GitHub Actions workflow (runs 1st–3rd of each month at midnight SGT)
- `utilities/content_export/content-db.json` — generated content database (see below); do not hand-edit, regenerate instead

---

## Content Database (`utilities/content_export/`)

`content-db.json` is a generated, read-only snapshot of every page's long-form content, keyed by URL slug (e.g. `"/hearing-test"`). Each page entry is a flat, ordered list of `{level, heading, content}` blocks, one per H2–H6 heading and per FAQ/troubleshooting accordion panel (`<details class="panel">`). `content` is plain text — tags stripped, entities decoded, with list items flattened to `- item` lines, definition lists to `Term: Definition` lines, and tables to `cell | cell | cell` rows.

Deliberately excluded from every page, since none of it is backed by heading markup: the `<h1>` and its lead/intro paragraph, the interactive tool controls, sidebar testimonials/review-form chrome, the live device-readout panel on `show-mic.html`/`show-speakers.html` (`id="device-details"`), and any "Related ... Tools" card grid (same navigational-chrome exemption CLAUDE.md already applies to sidebar "Related Tools" cards, see below).

Regenerate after editing any page's content:
```bash
python3 utilities/content_export/export_content_db.py
```
The generator (`export_content_db.py`) is dependency-free (stdlib `html.parser` only, no bs4/lxml), consistent with the site's no-build-step, no-package-manager setup.

---

## Internal Linking Strategy — Advanced Silo

Three-level authority silo. Every inline body content link uses the target page's **primary keyword as anchor text** (no "click here" / "read more"). The silo plan governs **body content links only**.

**Sidebar / nav / footer links are expected and acceptable.** Per Kyle Roof's SEO methodology, search engines discount links in nav, footer, and sidebar as navigational — they do not pass the same authority as in-content links and do not interfere with the silo structure. Audits must focus exclusively on inline body content links; sidebar "Related Tools" cards and footer links must be ignored.

---

### Silo Structure (Static Reference)

The tables below show the **base/initial link structure**. In practice, all link targets rotate monthly — see the Monthly Rotation section. Use these tables as structural reference only (which page belongs to which silo, what each page's primary keyword is).

---

#### Pillar Page

`index.html` — **"mic test online"** (135,000/mo)

- Has exactly **1 outgoing body link** — to whichever hub is first in that month's shuffled hub order.
- All 3 hubs link **up** to the pillar every month; the anchor text rotates among 6 long-tail variants (each hub picks its own variant independently).
- The pillar never links to supporting pages directly.

---

#### Sub-Silo Hubs (3 hubs)

Each hub has exactly **4 body content slots**:

| Slot | Semantic role | Rotates? |
|------|--------------|----------|
| `slot_a` | Up to pillar — anchor rotates monthly among 6 long-tail variants (see below) | Yes |
| `slot_b` | Left hub neighbour — empty when this hub is first in monthly shuffled order | Yes |
| `slot_c` | Right hub neighbour — empty when this hub is last in monthly shuffled order | Yes |
| `slot_d` | Down to first supporter in this hub's shuffled chain | Yes |

| Hub | File | Primary Keyword | Volume |
|-----|------|----------------|--------|
| **A — Tone Generator** | `tone-generator.html` | "tone generator" | 49,500/mo |
| **B — Hearing Test** | `hearing-test.html` | "hearing test online" | 33,100/mo |
| **C — Audio Latency Test** | `audio-latency-test.html` | "audio latency test" | 3,600/mo |

---

#### Supporting Pages

Each supporting page has exactly **3 body content slots**:

| Slot | Semantic role | Rotates? |
|------|--------------|----------|
| `slot_a` | Up to this page's hub — anchor = hub's primary keyword | No (anchor fixed, sentence variant rotates) |
| `slot_b` | Second link — content depends on position in the shuffled chain (see table below) | Yes |
| `slot_c` | Third link — content depends on position; may be empty | Yes |

**slot_b / slot_c content by position in the monthly shuffled chain:**

| Position | slot_b | slot_c |
|----------|--------|--------|
| First in Silo A | next page in chain | **empty** — Silo A has no backward bridge |
| First in Silo B or C | next page in chain | backward bridge → last page of previous silo |
| Middle (not first, not last) | prev page in chain | next page in chain |
| Last in Silo A or B | prev page in chain | forward bridge → first page of next silo |
| Last in Silo C | prev page in chain | **empty** — Silo C has no forward bridge |

##### Silo A — Speaker & Headphone Testing (hub: `tone-generator.html`)

| Page | File | Primary Keyword | Volume |
|------|------|----------------|--------|
| Headphone Test | `headphone-test.html` | "headphone test" | 33,100/mo |
| Stereo Test | `stereo-test.html` | "stereo test" | 18,100/mo |
| Bass Test | `bass-test.html` | "bass test" | 12,100/mo |
| Speaker Volume Test | `speaker-volume-test.html` | "speaker test online" | 6,600/mo |
| Show My Speakers | `show-speakers.html` | "what speakers do i have" | 10/mo |

##### Silo B — Hearing & Sound Analysis (hub: `hearing-test.html`)

| Page | File | Primary Keyword | Volume |
|------|------|----------------|--------|
| Sound Level Meter | `sound-level-meter.html` | "sound level meter online" | 2,900/mo |
| Voice Frequency Analyzer | `voice-frequency-analyzer.html` | "voice frequency analyzer" | 110/mo |
| Background Noise Analyzer | `background-noise-analyzer.html` | "background noise analyzer" | <10/mo |

##### Silo C — Microphone Tools (hub: `audio-latency-test.html`)

| Page | File | Primary Keyword | Volume |
|------|------|----------------|--------|
| Mic Recorder | `mic-recorder.html` | "online mic recorder" | 2,900/mo |
| Echo Test | `echo-test.html` | "echo test" | <10/mo |
| Show My Microphone | `show-mic.html` | "what microphone do i have" | <10/mo |

---

#### Bridges Between Silos

Bridges are **bidirectional** and connect the last page of one silo's shuffled chain to the first page of the next silo's shuffled chain. The anchor text is always the target page's own primary keyword. Bridge targets change monthly as the supporter shuffle changes which pages land in the first/last positions.

| Bridge | Direction | Notes |
|--------|-----------|-------|
| Silo A ↔ Silo B | last of shuffled A ↔ first of shuffled B | both directions, targets change monthly |
| Silo B ↔ Silo C | last of shuffled B ↔ first of shuffled C | both directions, targets change monthly |
| Silo C → (none) | last of shuffled C has no forward bridge | Silo C is the final silo |

---

## Monthly Rotation System

### Purpose

The monthly rotation prevents stale internal link patterns by shuffling:

1. **Hub order** — determines which hub the pillar links to, and each hub's left/right neighbors
2. **Supporter order within each silo** — changes the prev/next chain, which hub's `slot_d` points to, and which pages hold the bridge positions

### Script

**File:** `utilities/silo_linking/generate_silo_rotation.py`

**Run manually:**
```bash
# Preview without writing
python3 utilities/silo_linking/generate_silo_rotation.py --dry-run

# Apply this month's rotation
python3 utilities/silo_linking/generate_silo_rotation.py
```

### GitHub Actions Trigger

**File:** `.github/workflows/silo-rotation.yml`

```yaml
on:
  schedule:
    - cron: '0 16 1-3 * *'   # midnight SGT (UTC+8), days 1–3 of each month
  workflow_dispatch:           # also triggerable manually from the GitHub UI
```

Runs on days 1, 2, and 3 as a retry safety net. The workflow commits only when `git diff` shows actual changes, so repeated runs are safe. Uses the built-in `GITHUB_TOKEN` — no PAT required.

---

### HTML Comment Markers

Every silo link lives between HTML comment markers injected directly into each page's body content paragraph. The script replaces the content between markers each month:

```html
<!-- SILO_START:slot_a -->sentence with <a href="/url">anchor text</a><!-- SILO_END:slot_a -->
```

**First run behaviour:** If a marker does not yet exist in the HTML, the script inserts it immediately before the closing `</p>` tag of the first paragraph following the designated heading (see Injection Targets table below).

**Subsequent runs:** The script finds the existing marker by name and replaces only the content between `SILO_START` and `SILO_END`. The surrounding HTML is never touched.

**Empty slots:** When a slot has no link this month (e.g. first of Silo A has no backward bridge), the script writes empty content between the markers: `<!-- SILO_START:slot_c --><!-- SILO_END:slot_c -->`. This keeps the marker in the HTML so future months can fill it in.

---

### Slot Injection Targets

Physical location in each HTML file where each slot's marker is inserted on first run. These headings never change — only the content between the markers changes monthly.

| Page | slot_a | slot_b | slot_c | slot_d |
|------|--------|--------|--------|--------|
| `index.html` | after `<h1>` | — | — | — |
| `tone-generator.html` | after `<h1>` | H2 "What Is a Tone Generator?" | H3 "Hearing Range Assessment" | H3 "Tinnitus Frequency Matching" |
| `hearing-test.html` | after `<h1>` | H2 "How to Take the Hearing Test" | H2 "Understanding Your Hearing Test Results" | H2 "Common Causes of High-Frequency Hearing Loss" |
| `audio-latency-test.html` | after `<h1>` | H2 "What Is Audio Latency?" | H2 "Audio Latency by Use Case" | H2 "How to Reduce Audio Latency" |
| `headphone-test.html` | after `<h1>` | H2 "What Does the Headphone Test Check?" | H3 "Sound Coming from the Wrong Ear" | — |
| `stereo-test.html` | after `<h1>` | H2 "What Is Stereo Sound?" | H3 "Reversed Channels (Left/Right Swapped)" | — |
| `bass-test.html` | after `<h1>` | H2 "Understanding Bass Frequency Ranges" | H3 "No Bass Response at Low Frequencies" | — |
| `speaker-volume-test.html` | after `<h1>` | H3 "Speaker Channel Test" | H3 "Low Volume Speaker Test" | — |
| `show-speakers.html` | after `<h1>` | H2 "How to Find Out What Speakers You Have" | H3 "Device Name and Group ID" | — |
| `sound-level-meter.html` | after `<h1>` | H2 "What Is a Decibel?" | H2 "Sound Level Guide" | — |
| `voice-frequency-analyzer.html` | after `<h1>` | H3 "Fundamental Frequency" | H3 "Checking Microphone Frequency Response on Calls" | — |
| `background-noise-analyzer.html` | after `<h1>` | H3 "What Causes Noise in Each Frequency Band" | H3 "Low-Frequency Noise: HVAC" | — |
| `mic-recorder.html` | after `<h1>` | H2 "What Is an Online Mic Recorder" | H2 "Online Mic Recorder Privacy" | — |
| `echo-test.html` | after `<h1>` | H2 "Understanding Audio Echo" | H3 "Acoustic Echo" | — |
| `show-mic.html` | after `<h1>` | H2 "How to Find Out What Microphone You Have" | H3 "Device Name — What Microphone Do I Have?" | — |

---

### Rotation Algorithm (Deterministic)

All shuffles are reproducible — the same year/month always produces the same order. Seeds come from MD5 hashes so there are no external dependencies.

#### 1. Hub slot_a anchor selection (up to pillar)

Each hub picks one of 6 long-tail anchor variants independently each month:

```
"mic test online", "online microphone test", "free microphone test",
"test my microphone", "microphone test online", "mic check online"
```

```python
seed = int(MD5(f"{year}-{month}-{hub_file}-slot_a"), 16)
anchor = HUB_UP_ANCHORS[seed % 6]
```

Each anchor has 6 dedicated sentence templates in `SENTENCES`, so prose always reads naturally.

#### 3. Hub order shuffle → pillar link + hub horizontal links

```python
seed = int(MD5(f"{year}-{month}-pillar"), 16)
shuffled_hubs = random.Random(seed).shuffle(HUBS)
# HUBS = ["tone-generator.html", "hearing-test.html", "audio-latency-test.html"]
```

Result for each position `pos` in `shuffled_hubs`:

| pos | slot_b (left) | slot_c (right) | slot_d (down) |
|-----|--------------|---------------|---------------|
| 0 (first) | empty | `shuffled_hubs[1]` | first of this hub's shuffled supporter chain |
| 1 (middle) | `shuffled_hubs[0]` | `shuffled_hubs[2]` | first of this hub's shuffled supporter chain |
| 2 (last) | `shuffled_hubs[1]` | empty | first of this hub's shuffled supporter chain |

Pillar `slot_a` → `shuffled_hubs[0]` (the first hub this month).

#### 4. Supporter order shuffle → hub down link + prev/next chain + bridges

```python
# seed_key: "silo_0" for Silo A, "silo_1" for Silo B, "silo_2" for Silo C
seed = int(MD5(f"{year}-{month}-silo_{i}"), 16)
shuffled = random.Random(seed).shuffle(silo_supporters)
```

- Hub `slot_d` → `shuffled[0]` (first in shuffled chain)
- Each supporter's `slot_b` / `slot_c` assigned per the position rules table above
- Bridge anchors use the target page's own primary keyword (changes monthly as first/last positions change)

#### 5. Sentence template selection → which of 6 variants is used

```python
seed = int(MD5(f"{year}-{month}-{source_file}-{anchor}"), 16)
idx = seed % 6
sentence = SENTENCES[anchor][idx]
```

There are **6 sentence templates per anchor keyword** × 15 anchor keywords = 90 templates total. The sentence text rotates monthly even when the link target is the same, so the surrounding prose always reads fresh.

---

## Silo Audit Guide

When checking silo compliance always use **body content links only** — ignore nav, footer, and sidebar cards.

**Expected outgoing body link counts:**

| Page | Expected count | Notes |
|------|---------------|-------|
| Pillar (`index.html`) | exactly 1 | to the current month's first hub |
| Each hub page | exactly 4 | slot_a (up) + slot_b + slot_c + slot_d; slot_b or slot_c may be empty but marker must exist |
| Each supporter page | exactly 3 | slot_a (up) + slot_b + slot_c; slot_c may be empty for first-of-A or last-of-C |

**Hard rules that must never be violated:**

- A supporter must never link directly to the pillar (`/` or `index.html`)
- A supporter must never link to a page in a different silo except via the designated bridge slots
- Only the **last** supporter of Silo A or B may hold a forward bridge (slot_c)
- Only the **first** supporter of Silo B or C may hold a backward bridge (slot_c)
- No page may link to itself
- Hub pages must not link to supporters belonging to a different hub's silo

---

## W3 HTML Validator — Pending

All pages should be validated using live URLs via the Nu HTML Checker:
```
https://validator.w3.org/nu/?doc=https://mic-tests.github.io/<page-path>
```

Example: `https://validator.w3.org/nu/?doc=https://mic-tests.github.io/`

No pages have been validated yet. After each deploy, re-run the validator on changed pages to catch any new issues.
