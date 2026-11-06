# Changelog

Notable changes to scootr's laboratory, newest first. The site was rebuilt from
scratch on 2026-05-20; the 2020–2023 history in `git log` is the earlier site.
Dates are commit dates.

## 2026-11-05

### Added
- **About:** current employer named (Luften) and a Resume download in the contact
  row (`about/Scott_Morris_Resume.pdf`).
- **Every page:** favicon cut from `earth-loop.mp4` — a 16-frame spin that animates
  in the tab (pauses while the tab is hidden); meta descriptions; Open Graph tags
  on home, about and projects so shared links render as cards.
- **Homepage:** "in progress" tag on the Elysium nav entry.
- **scootr.fm:** `tools/build_playlist.py` generates `data/playlist.json`
  (explicit-CC-license gate, exact durations, stream/CORS verification).
- **scootr.fm:** Spotify and Apple Music links. Apple Music matches are resolved at
  build time; Spotify needs `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` set
  locally (written, not yet run against the real API). Tracks without a confirmed
  match get a "search spotify" link.
- **scootr.fm (mobile):** labeled tune in/out buttons, a touch cheat-sheet, and
  decorative menu items hidden on small screens.

### Changed
- **scootr.fm:** the crate is now 181 tracks / ~18.4 h across 44 releases of
  atmospheric jungle and drum & bass (Mastik, Eternal Sunset, Omega Dub Experience
  and others). Breakcore, dancehall, jump-up, neurofunk and techstep releases were
  dropped.

### Removed
- **scootr.fm:** all synthesized tracker-module slots and the chiptune/libopenmpt
  and Mod Archive dependencies. Every slot is a real recording.

### Fixed
- **scootr.fm (iOS):** music stopped when the browser was backgrounded or the
  screen locked. The `<audio>` element is now kept out of the Web Audio graph on
  phones, tracks chain off `ended`, and the page resyncs to the broadcast clock
  on return.
- **scootr.fm:** archive.org metadata is escaped before it reaches `innerHTML`; a
  slot whose file ends slightly short of its scheduled time is no longer reloaded
  in a loop.

## 2026-07-16

### Added
- **The Vigil:** live worldwide crisis map (USGS / EONET / WHO feeds plus a baked
  GDACS snapshot), with loading state, zoom-gated labels and background refresh.
- **scootr.fm:** 24/7 clock-synced pirate radio — a fixed epoch and arithmetic keep
  every listener on the same second. Built up over the day (v1–v4): a Windows
  Media Player-style player, album-art tint, playlist air times, sleep timer,
  share, cinema mode (`□` / `f`), idle auto-cinema, a pop-out mini player, a
  deterministic per-cycle reshuffle, and a Last.fm "receiver" panel.
- **scootr.fm:** nine beat-reactive visualizations — corridor, wormhole, inkblot,
  battery, starburst, the signal, bars & waves, alchemy, phase scope.
- **Homepage:** scootr.fm replaces Signal in the nav, with a live on-air ticker.

### Changed
- **scootr.fm:** the visualization gallery was rebuilt around the WMP/Winamp era;
  the scene-style "grid" and "yard" modes were retired.

### Fixed
- **scootr.fm:** the watchdog no longer restarts tracks that are still buffering;
  inkblot no longer whites out.

## 2026-07-15
- **Homepage:** interstellar warp intro.
- **The Grievance Atlas:** interactive map of 3.3 million NYC 311 complaints.

## 2026-07-07
- Homepage nav reordered to lead with About and Projects; `CLAUDE.md` added.

## 2026-06-25 – 2026-06-30
- Pages: racial-bias dashboard, Elysium teaser, About dossier, Signal
  (audio-reactive 3D node flythrough), Lead Intelligence System, and the
  Multi-Brand Ops Dashboard demo; projects index redesigned.
- Fixed the light/dark toggle on the retail dashboard demo and removed company
  names from the leads screenshots.

## 2026-05-20 – 2026-05-26 — relaunch
- Site rebuilt from scratch as "scootr's laboratory": looping Earth video
  background, film grain, social icons, countdown timer, Call of Duty crosshair
  and hitmarker sound, forced `cursor: none`, mobile readability fixes.
