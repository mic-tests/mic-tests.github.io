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
- `css/common.css` — shared component styles (footer, cards, status indicators)
- `css/style.css` — HTML5 Boilerplate base reset (not project-specific)
- Bootstrap 5.3.0-alpha1 and Bootstrap Icons 1.11.1 are loaded via CDN (jsdelivr)
- Many pages also duplicate common styles (e.g. `.footer`) in their own `<style>` blocks

### SEO Structure
Each page should have:
- A canonical `<link>` tag
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

## Internal Linking Strategy — Advanced Silo

Three-level authority silo. Every link uses the target page's **primary keyword as anchor text** (no "click here" / "read more"). The silo plan governs **body content links only**.

**Sidebar / nav / footer links are expected and acceptable.** Per Kyle Roof's SEO methodology, search engines discount links in nav, footer, and sidebar as navigational — they do not pass the same authority as in-content links and do not interfere with the silo structure. Audits should focus exclusively on inline body content links; sidebar "Related Tools" cards and footer links can be ignored.

### Pillar Page

`index.html` — **"mic test online"** (135,000/mo)

| Direction | Links to | Anchor text |
|-----------|----------|-------------|
| Down | `tone-generator.html` | "tone generator" |

Only 1 outgoing link. This hoards all authority on the pillar.

### Sub-Silo Hubs (3 hubs)

Ordered by volume. Each hub links **up** to pillar, **horizontal** to adjacent hubs, and **down** to its first supporting page.

| Hub | File | Volume | Up (pillar) | Left | Right | Down (1st supporting) |
|-----|------|--------|-------------|------|-------|-----------------------|
| **A — Tone Generator** | `tone-generator.html` | 49,500 | "mic test online" | — | "hearing test online" | "headphone test" |
| **B — Hearing Test** | `hearing-test.html` | 33,100 | "mic test online" | "tone generator" | "audio latency test" | "sound level meter online" |
| **C — Audio Latency Test** | `audio-latency-test.html` | 3,600 | "mic test online" | "hearing test online" | — | "online mic recorder" |

### Supporting Pages

Ordered by volume within each silo. Each supporting page links **up** to its hub and **horizontal** to prev/next in its chain. Supporting pages **never** link directly to the pillar.

#### Silo A — Speaker & Headphone Testing (hub: Tone Generator)

| # | Page | File | Volume | Up (hub) | Prev | Next |
|---|------|------|--------|----------|------|------|
| 1 | Headphone Test | `headphone-test.html` | 33,100 | "tone generator" | — | "stereo test" |
| 2 | Stereo Test | `stereo-test.html` | 18,100 | "tone generator" | "headphone test" | "bass test" |
| 3 | Bass Test | `bass-test.html` | 12,100 | "tone generator" | "stereo test" | "speaker test online" |
| 4 | Speaker Volume Test | `speaker-volume-test.html` | 6,600 | "tone generator" | "bass test" | "what speakers do i have" |
| 5 | Show My Speakers | `show-speakers.html` | 10 | "tone generator" | "speaker test online" | — |

#### Silo B — Hearing & Sound Analysis (hub: Hearing Test)

| # | Page | File | Volume | Up (hub) | Prev | Next |
|---|------|------|--------|----------|------|------|
| 1 | Sound Level Meter | `sound-level-meter.html` | 2,900 | "hearing test online" | — | "voice frequency analyzer" |
| 2 | Voice Frequency Analyzer | `voice-frequency-analyzer.html` | 110 | "hearing test online" | "sound level meter online" | "background noise analyzer" |
| 3 | Background Noise Analyzer | `background-noise-analyzer.html` | <10 | "hearing test online" | "voice frequency analyzer" | — |

#### Silo C — Microphone Tools (hub: Audio Latency Test)

| # | Page | File | Volume | Up (hub) | Prev | Next |
|---|------|------|--------|----------|------|------|
| 1 | Mic Recorder | `mic-recorder.html` | 2,900 | "audio latency test" | — | "echo test" |
| 2 | Echo Test | `echo-test.html` | <10 | "audio latency test" | "online mic recorder" | "what microphone do i have" |
| 3 | Show My Microphone | `show-mic.html` | <10 | "audio latency test" | "echo test" | — |

### Bridges Between Silos

The last supporting page of one silo links to the first supporting page of the next silo, and vice versa. Linear only — last silo does NOT bridge back to first.

| From (last of silo) | To (first of next silo) | Anchor |
|----------------------|-------------------------|--------|
| Show My Speakers (last A) → | Sound Level Meter (first B) | "sound level meter online" |
| Sound Level Meter (first B) → | Show My Speakers (last A) | "what speakers do i have" |
| Background Noise Analyzer (last B) → | Mic Recorder (first C) | "online mic recorder" |
| Mic Recorder (first C) → | Background Noise Analyzer (last B) | "background noise analyzer" |

### Total: 37 links across 15 pages

---

## W3 HTML Validator — Pending

All pages should be validated using live URLs via the Nu HTML Checker:
`https://validator.w3.org/nu/?doc=https://mic-tests.github.io/<page-path>`

Example:
- `https://validator.w3.org/nu/?doc=https://mic-tests.github.io/`

No pages have been validated yet. After each deploy, re-run the validator on changed pages to catch any new issues.
