# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Scott Morris's personal portfolio site (`scootr's laboratory`), deployed from `github.com/scottdmorris/scootr`. Pure static HTML/CSS/JS — no framework, no bundler, no `package.json`. Each page is a single self-contained `.html` file with inline `<style>` and `<script>` blocks.

## Commands

There is no build step. To preview locally, serve the directory root with any static file server, e.g.:

```
python -m http.server 8000
```

Then open `http://localhost:8000/index.html` (or `/about/index.html`, `/projects/index.html`, etc.). There are no lint or test commands — verify changes by loading the page in a browser.

## Structure

- `index.html` — homepage ("scootr's laboratory"), nav links to About, Projects, Elysium, scootr.fm; shows a live "on air" ticker computed from the radio playlist.
- `about/index.html` — bio / resume-style "dossier" page (experience, education, skills, contact links).
- `projects/index.html` — project index, links out to individual project subdirectories:
  - `projects/racial-bias/` — ML fairness project (FairFace/Grad-CAM), includes static JSON data files and generated image assets under `img/`.
  - `projects/leads/` — Lead Intelligence System write-up.
  - `projects/retail-dashboard/` — multi-brand ops dashboard demo write-up.
  - `projects/311/` — The Grievance Atlas, NYC 311 complaint map (static JSON under `data/`, live Socrata fetch).
  - `projects/vigil/` — The Vigil, live worldwide crisis map (USGS/EONET/WHO live feeds + baked GDACS snapshot under `data/`).
  - `projects/radio/` — scootr.fm, 24/7 clock-synced pirate radio (playlist under `data/`, streams from archive.org + Mod Archive; homepage on-air ticker reads its `data/playlist.json`).
- `elysium/index.html`, `signal/index.html` — standalone creative/experimental pages, linked from the homepage nav but not part of the "Projects" listing.

Each top-level section lives in its own directory with its own `index.html`; there is no shared layout, template, or component system — new pages are built by copying an existing page and editing in place.

## Design system (duplicated per-file, not shared)

Every page reimplements the same visual language independently — there is no shared CSS file, so changes to the aesthetic must be repeated by hand across every `index.html` that needs them:

- Color tokens defined per-page as CSS variables: `--off-white`, `--dim`, `--dimmer`, `--border` (dark theme, off-white text on black).
- Fonts: `Cormorant Garamond` (serif, headings/body) + `Courier Prime` (monospace, labels/tags/UI chrome), loaded from Google Fonts via `<link>`.
- Recurring layered background effects, each its own `<canvas>`/`<div>` with matching JS: `#grain` (canvas noise texture), `#vignette` (radial gradient), and on some pages `#scanlines` (CRT-style repeating gradient).
- Fade-up entrance animation (`@keyframes fade-up`) with staggered `animation-delay` used throughout for hero text and list items.
- Shared page footer pattern: an inline-SVG icon row linking to GitHub/Instagram/LinkedIn/email, and a `#back` link back to the parent page.

When editing the visual style (colors, effects, fonts), check whether the change should be mirrored across `index.html`, `about/index.html`, `elysium/index.html`, `projects/index.html`, and `signal/index.html` — they are not derived from a common source.

## Content notes

- The About page intentionally redacts the current employer name (shown as `[REDACTED]` in the Service Record) — this is deliberate, not a placeholder to fill in. Do not "fix" it by naming the employer unless explicitly asked.
- Large binary assets (`.mp4` video backgrounds, `.mp3` sound effect) are committed directly to the repo root and referenced by relative path from `index.html`.
