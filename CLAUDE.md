# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**MicTest** is a static website served from the custom domain https://mictest.dev (migrated from `mic-tests.github.io` on 2026-08-02 — see Custom Domain section below). It provides browser-based audio testing tools (microphone, speaker, headphone, hearing tests) using the Web Audio API.

As of 2026-08-31 the site runs on a **JSON-driven build pipeline** (`src/` → `public/`) rather than hand-authored HTML files — see Architecture below. The pre-migration hand-authored site (Bootstrap 5, DM Sans/Syne fonts) is preserved read-only in `legacy-bootstrap-site/`; it is **not** served and should not be edited.

## Deployment

This is a static site with a small Python build step — there's still no Node/npm toolchain, transpilation, or minification.

**Build order matters.** Run all three, in this order, whenever `src/content/*.json` changes:

```bash
python3 src/build_data.py                          # (re)writes src/data/{tools,pages,site}.json from src/content/
python3 src/generate.py                             # renders src/template*.html + src/data/*.json -> public/
python3 utilities/silo_linking/generate_silo_rotation.py   # patches this month's silo links into public/*.html (last step)
```

`generate_silo_rotation.py` must run **after** `generate.py`, not before — it patches the already-rendered `public/*.html` files in place via comment markers, and never touches `src/content/`. Running `generate.py` again without re-running the rotation script afterward will silently revert the current month's rotation back to whatever's baked into each page's `src/content/<slug>.json`.

Then commit the changes under `public/` (and `src/data/*.json` if `build_data.py` changed them) and push to `main`. Committing `public/` is still good practice — it's what `cd public && python3 -m http.server` serves for local preview (see Local Development below) and gives the rendered output its own history — but as of the deploy workflow below, it's no longer what's actually live: the production site never depends on whatever happens to be committed there.

**GitHub Pages deploy — `.github/workflows/deploy.yml`.** GitHub Pages can't serve an arbitrary `/public` folder directly (only the repo root, a `/docs` folder, or a GitHub Actions publish step), so this repo uses the Actions route: on every push to `main` that touches `src/**` or `utilities/silo_linking/**` (or via manual `workflow_dispatch`), the workflow runs the exact three-step build order above from scratch on a clean runner — `build_data.py` → `generate.py` → `generate_silo_rotation.py` — then publishes the freshly generated `public/` via `actions/deploy-pages`. Because it always rebuilds from `src/content/` itself rather than trusting the committed `public/` snapshot, a human forgetting a build-order step locally (or forgetting to re-run the silo rotation after a rebuild — see `utilities/silo_linking/generate_silo_rotation.py`'s note below) can no longer leave the *live* site stale, even if the local commit under `public/` is momentarily out of sync.

**⚠️ One-time manual step required, not done yet:** the workflow only takes effect once Pages' source is switched to "GitHub Actions" in the repo's Settings → Pages — this can't be done via the API/CLI available in this environment and must be flipped by a repo admin in the GitHub UI. Until that switch is flipped, check the actual GitHub Pages source setting before assuming what's serving the production site — do not assume `deploy.yml` is live just because it exists in the repo.

### Custom Domain

The site moved from `mic-tests.github.io` to `mictest.dev` on 2026-08-02. Key points for anyone touching URLs, SEO metadata, or DNS:

- `CNAME` is now **generated**, not a hand file — `src/generate.py`'s `write_robots_and_sitemap()` writes `public/CNAME` from `site.json`'s `domain` field. Once Pages is actually serving `public/`, this is what GitHub Pages will read to serve the custom domain. Don't hand-create a `CNAME` file elsewhere; change `domain` in `src/build_data.py` (`DOMAIN` constant, which `build_data.py` writes into `src/data/site.json`) instead.
- DNS is managed in Cloudflare. The apex (`mictest.dev`) and `www` records are `A`/`AAAA`/`CNAME` set to **DNS only** (grey cloud, not proxied) — this is required for GitHub Pages to issue and renew its own HTTPS certificate. Do not re-enable Cloudflare proxying on these records without accounting for cert renewal.
- `mic-tests.github.io` still works and 301-redirects automatically to `mictest.dev` (GitHub Pages' built-in behavior once a custom domain is set) — no manual redirect config needed.
- `www.mictest.dev` similarly redirects to the apex automatically via GitHub Pages.
- Canonical `<link>` tags and JSON-LD `url`/`logo` fields are generated per-page from `site.json`'s `domain` — always `https://mictest.dev/...`, never the old `.github.io` domain. `sitemap.xml` and `robots.txt` are likewise generated (see Key Files below), not hand-maintained.

## Local Development

Serve locally with any HTTP server (file:// URLs may block microphone access due to browser security), pointed at `public/` — not the repo root, since the repo root no longer holds servable pages:

```bash
cd public
python3 -m http.server 8000
# or
npx serve .
```

Extensionless routes (`/tone-generator` etc.) only resolve automatically under GitHub Pages, not under a plain local file server — append `.html` when testing locally (e.g. `http://localhost:8000/tone-generator.html`).

There are no linters, test suites, or package managers configured.

## Architecture

### JSON-Driven Build Pipeline

Single source of truth, modeled on the passwordhive/hexcalculator pattern:

- **`src/content/<slug>.json`** — one tool page's *entire* content: meta title/description/keywords, hero eyebrow/H1/intro, the nameplate stats, the tool card's own interactive markup, sidebar HTML, `content_blocks` (long-form sections), FAQ, JSON-LD, an optional `extra_style` block for page-specific CSS overrides, and that tool's own fully self-contained JS (the `script` field — rendered into the page's single `<script>{{TOOL_SCRIPT}}</script>` tag; this field must **not** include its own `<script>`/`</script>` wrapper).
- **`src/content/pages/<slug>.json`** — same idea for the 4 simpler info pages (`about`, `contact`, `troubleshooting`, `sitemap`).
- **`src/template.html`** — shared template for the 15 tool pages (rail nav, mobile drawer, footer, theme toggle, comments widget, and all base/component CSS — edited **once**, not copy-pasted per page).
- **`src/template-page.html`** — shared template for the 4 info pages + `404.html`. Keep its component CSS (`.btn-*`, `.status-message`, `.alert-*`, forms, etc.) in sync with `src/template.html`'s — it's easy for one to drift ahead of the other since they're two separate `<style>` blocks, not a shared stylesheet.
- **`src/static/`** — binary/opaque assets that can't be derived from `site.json`: `favicon.ico`, `icon.png`, `icon.svg`, the Google Search Console verification file (`googlecb346f17d96186ee.html` — do not modify). Copied verbatim into `public/` by `generate.py`.
- **`src/build_data.py`** — assembles `src/data/{tools,pages,site}.json` from `src/content/`. Site-wide constants (`SITE_NAME`, `DOMAIN`, `HOME_SLUG`, `ADSENSE_PUBLISHER_ID`) live at the top of this file.
- **`src/generate.py`** — renders `src/data/*.json` + the two templates into `public/*.html`, plus generates `public/robots.txt`, `public/sitemap.xml`, `public/CNAME`, and `public/ads.txt` (all derived from `site.json`, never hand-edited), plus `public/404.html` (built from a dedicated `render_404()` — there's no `src/content/pages/404.json`, since the 404 page isn't part of the tools/pages content model).
- **`public/`** — generated output, committed. Never hand-edit anything here — edit `src/content/<slug>.json` (or the template/generator) and rerun the build (see Deployment above).

Adding a new tool page means: write `src/content/<new-slug>.json`, add its slug to `TOOL_SLUGS` in `src/build_data.py`, add its nav link to both the desktop rail and mobile drawer `<nav>` blocks in **both** `src/template.html` and (if it should also appear on info pages' nav, which it should) `src/template-page.html`, then run the full build.

### Per-Page Audio Logic
Each tool's JavaScript is fully self-contained in that tool's `src/content/<slug>.json` `script` field — it becomes the page's single inline `<script>` tag on render. The Web Audio API is the core technology: `getUserMedia` for mic input, `AnalyserNode` for frequency data, `OscillatorNode` for tone generation, `MediaRecorder` for recording.

### Styling
All CSS lives inline in the two templates' `<style>` blocks (design tokens as CSS custom properties, themed for light/dark via `prefers-color-scheme` and a `data-theme` override) — there is no separate stylesheet to load or maintain. External dependencies are CDN-only: Tailwind's Play CDN (`cdn.tailwindcss.com`, with the Typography plugin for `.prose` long-form content) and Bootstrap Icons. Google Fonts serves JetBrains Mono (headings/mono UI) and IBM Plex Sans (body).

Per-page CSS overrides (mostly for the handful of tools whose runtime JS sets literal legacy Bootstrap-style class names) go in that tool's `extra_style` field in its content JSON, rendered into the `{{PAGE_STYLE}}` slot — always using the shared CSS custom properties (`var(--amber)`, `var(--panel)`, etc.), never hardcoded colors, so it stays correct in both themes.

The old `css/common.css` / `css/design.css` / `css/style.css` (Bootstrap-era stylesheets) are archived under `legacy-bootstrap-site/css/` and are not used by the current pipeline.

### SEO Structure
Each page gets, automatically from its content JSON + the shared template — no per-page manual bookkeeping required:
- A canonical `<link>` tag using an extensionless URL (e.g. `https://mictest.dev/tone-generator`)
- JSON-LD structured data (Schema.org `WebPage`/`SoftwareApplication`, plus `FAQPage` when the page has FAQ items)
- Meta description (all pages) and meta keywords (tool pages only — `template-page.html`'s info pages don't render a keywords meta tag)
- An entry in the generated `sitemap.xml`

### Legacy archive (`legacy-bootstrap-site/`)
A frozen, read-only snapshot of the pre-migration hand-authored site: the original 19 tool/info pages + `404.html`, `css/`, `js/`, and the old root-level `CNAME`/`ads.txt`/`robots.txt`/`sitemap.xml`. Kept for reference/history only — it is not linked from the build, not served, and should not be edited. `legacy-bootstrap-site/content_export/` holds the old content-export tooling (`export_content_db.py` + its `content-db.json` output), which read root-level page filenames directly and is now broken by the file move; it predates the JSON content model and was already unwired from the pipeline before the move — treat it as historical, not something to fix and run.

### Design exploration (`design-mockups/`)
Three standalone HTML mockups (`1-waveform-lab.html`, `2-studio-paper.html`, `3-signal.html`) explored while designing the homepage's current "instrument-panel" Tailwind template. Not linked from the build, not part of the pipeline, and not referenced by any generated page — kept at repo root purely as design-decision reference. Don't wire these into the build; the shipped design lives in `src/template.html` / `src/content/index.json`.

## External Dependencies (CDN only)

| Dependency | Version | Purpose |
|---|---|---|
| Tailwind CSS (Play CDN) | latest, `?plugins=typography` | Utility classes + `.prose` long-form content styling |
| Bootstrap Icons | 1.11.1 | Icon set |
| Google Fonts | — | JetBrains Mono + IBM Plex Sans |
| Google AdSense | — | Monetization (publisher ID set once, in `src/build_data.py`'s `ADSENSE_PUBLISHER_ID` — flows into `site.json` → `{{ADSENSE_CLIENT}}` template token and generated `public/ads.txt`) |

Bootstrap (CSS framework, not the icon set) and DM Sans/Syne fonts are only used by the archived `legacy-bootstrap-site/` — not loaded by the current pipeline.

## Key Files

- `src/data/site.json` — **generated** by `build_data.py` from constants at the top of that file (`SITE_NAME`, `DOMAIN`, `HOME_SLUG`, `ADSENSE_PUBLISHER_ID`). Don't hand-edit `src/data/*.json` — edit the source (`src/build_data.py` constants or `src/content/`) and rerun the build.
- `public/sitemap.xml`, `public/robots.txt`, `public/CNAME`, `public/ads.txt` — all **generated** by `src/generate.py` from `src/data/site.json` + the tools/pages lists. Never hand-edit; change the source and rebuild.
- `src/static/googlecb346f17d96186ee.html` — Google Search Console verification (do not modify; copied verbatim into `public/`)
- `utilities/silo_linking/generate_silo_rotation.py` — monthly rotation script; patches `public/*.html` in place (see Deployment's build-order note)
- `.github/workflows/silo-rotation.yml` — GitHub Actions workflow (runs 1st–3rd of each month at midnight SGT); commits the rotated `public/*.html` back to `main` so the repo's own `public/` snapshot stays in sync for local preview/history
- `.github/workflows/deploy.yml` — GitHub Actions workflow that builds and publishes the live site (see Deployment above); runs the full `build_data.py` → `generate.py` → `generate_silo_rotation.py` sequence fresh on every relevant push and deploys via `actions/deploy-pages`, independent of whatever's committed under `public/`

---

## Internal Linking Strategy — Advanced Silo

Three-level authority silo. Every inline body content link uses the target page's **primary keyword as anchor text** (no "click here" / "read more"). The silo plan governs **body content links only**. All of the following operates on the generated `public/*.html` files (the filenames below, e.g. `tone-generator.html`, are unchanged from the pre-migration site — only their directory changed, from repo root to `public/`).

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

**File:** `utilities/silo_linking/generate_silo_rotation.py` — runs as the **last** step of the build, after `src/generate.py` (see Deployment's build-order note above).

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

**Note:** this workflow only runs `generate_silo_rotation.py` against whatever's already committed in `public/*.html` — it does not itself run `build_data.py`/`generate.py`. If content JSON changes and the full build hasn't been committed first, the rotation script will be patching stale rendered output *in that commit*. This no longer affects the live site (see Deployment's `deploy.yml`, which rebuilds everything from `src/content/` independently on every relevant push) — but it does mean this workflow's own commits to `public/*.html` can drift from `src/content/` if the full local build order wasn't followed beforehand, which is still worth avoiding for repo history/local-preview accuracy.

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

Physical location in each `public/*.html` file where each slot's marker is inserted on first run. These headings never change — only the content between the markers changes monthly.

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
https://validator.w3.org/nu/?doc=https://mictest.dev/<page-path>
```

Example: `https://validator.w3.org/nu/?doc=https://mictest.dev/`

No pages have been validated yet. Once Pages is serving the new pipeline's output (see Deployment), re-run the validator on changed pages after each deploy to catch any new issues.
