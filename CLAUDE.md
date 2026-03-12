# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**MicTest** is a static website hosted on GitHub Pages at https://mic-tests.github.io. It provides 18 browser-based audio testing tools (microphone, speaker, headphone, hearing tests) using the Web Audio API.

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
All pages are self-contained HTML files with inline or embedded CSS/JS. There is no transpilation, bundling, or minification step — files are served as-is.

### Partial Loading Pattern
The navbar, footer, and comments are stored in `partials/` and dynamically injected at runtime via `js/partials-loader.js` using `fetch()`. Every HTML page includes a script tag loading this file. Changes to shared UI elements should be made in:
- `partials/navbar.html`
- `partials/footer.html`
- `partials/comments.html`

### Per-Page Audio Logic
Each tool page is standalone — all its JavaScript lives inline in that page's `<script>` tag. The Web Audio API is the core technology: `getUserMedia` for mic input, `AnalyserNode` for frequency data, `OscillatorNode` for tone generation, `MediaRecorder` for recording.

### Shared Styles
- `css/common.css` — shared component styles (footer, cards, status indicators)
- `css/style.css` — HTML5 Boilerplate base styles
- Bootstrap 5.3.0-alpha1 and Bootstrap Icons 1.11.1 are loaded via CDN (jsdelivr)

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
| Commentario | — | Comments system |

## Key Files

- `sitemap.xml` — update `<lastmod>` dates when pages change
- `robots.txt` — SEO robots directives
- `ads.txt` — AdSense publisher configuration
- `googlecb346f17d96186ee.html` — Google Search Console verification (do not modify)
