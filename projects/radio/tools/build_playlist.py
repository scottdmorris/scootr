#!/usr/bin/env python3
"""Rebuild ../data/playlist.json for scootr.fm from archive.org metadata.

Run from anywhere:   python projects/radio/tools/build_playlist.py

The station is a pure clock-sync broadcast, so the only thing this file has to
get right is: every track has a license, a correct duration, and a streamable
URL. The script therefore
  * refuses any release without an explicit Creative Commons license URL,
  * takes durations from archive.org, fully decoding with ffmpeg whenever
    archive.org has none or its number doesn't fit the file size,
  * verifies each stream answers (200/206) with CORS headers, dropping
    anything that doesn't instead of shipping a broken slot.

Curation lives in CRATE below. The brief: atmospheric / PlayStation-era jungle
and drum & bass (Wipeout, Ridge Racer, Photek / Bukem lineage) -- pads, amens,
rolling sub. No tracker/synthesized interludes: every slot is a real recording.
"""
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "data", "playlist.json")
EPOCH = 1752624000  # fixed forever -- every listener's clock hangs off this
IA = "https://archive.org"
VERIFY_ATTEMPTS = 3
VERIFY_WORKERS = 6
APPLE_DELAY_S = 3.2  # iTunes Search API allows roughly 20 requests a minute
SPOTIFY_DELAY_S = 0.4  # Spotify limits by rolling 30 s window; 429s are retried
SPOTIFY_ATTEMPTS = 3
APPLE_CACHE = os.path.join(HERE, "apple_links_cache.json")
SPOTIFY_CACHE = os.path.join(HERE, "spotify_links_cache.json")

Track = dict[str, Any]
Spec = dict[str, Any]

# ---------------------------------------------------------------------------
# The crate. One dict per release:
#   item  archive.org identifier
#   take  cap on tracks (picked evenly across the release); omit for all
#   only  explicit track list (substrings of file names, in play order)
#   skip  regex; matching titles/file names are dropped (dupes, remixes...)
# ---------------------------------------------------------------------------
CRATE = [
    # --- Mastik: the atmospheric / "artcore" drum & bass label ---------------
    dict(item="mstk001"), dict(item="mstk003"), dict(item="mstk004"),
    dict(item="mstk005"), dict(item="mstk006"), dict(item="mstk007"),
    dict(item="mstk008"), dict(item="mstk009"), dict(item="mstk010"),
    dict(item="mstk011"), dict(item="mstk012"), dict(item="mstk013"),
    dict(item="mstk014"), dict(item="mstk015"),
    # --- Eternal Sunset: modern atmospheric / liquid / jazzy jungle ----------
    dict(item="towards-the-dawn", take=9),
    dict(item="symmetry_2025", take=6, skip=r"remix"),
    dict(item="flowers_and_charms_of_the_chinese-garden", take=5),
    dict(item="fogs_of_forgetfulness_202409", take=5),
    dict(item="eternal-wasteland", take=4, skip=r"remix"),
    dict(item="Nagai_yume_LP",
         only=["Cape_Canaveral", "Rain_Melancholy", "A_Sky_Full_Of_Stars", "Astral_travel"]),
    dict(item="10InTheDarkOfNight", only=["Rain_forest", "Glacier", "Oceania"]),
    dict(item="made-for-night-listening",
         only=["Starlight", "Water Drops", "Night train"]),
    # --- Omega Dub Experience: jazz-step / atmospheric jungle ----------------
    dict(item="siro614OmegaDubExperience-TheBankruptcyJazz"),
    dict(item="siro503OmegaDubExperience-LonelyWatersE.p",
         only=["Rainforests", "LonelyWaters"]),  # rest dupes Bankruptcy Jazz
    dict(item="siro693OmegaDubExperience-VictoryOverTheSun", skip=r"FarAwayFromTheSun"),
    # --- dark / ambient / intelligent jungle ---------------------------------
    dict(item="troorg004"),
    dict(item="qd-4271EvoEvolver-DystopianDream"),
    dict(item="turquoisedeath-kaleidoscope", take=6),
    dict(item="transient-stellar-rkodr", take=3),
    dict(item="SCL181", take=5),
    dict(item="acp027_vertical67_-_reflect", take=5),
    dict(item="SCL-TM004"),
    dict(item="rfr003"), dict(item="xgn031_-_beckett"),
    dict(item="xgn030_-_ricky_force_-_the_aerial_ep"),
    dict(item="tkep002"), dict(item="tkep010"),
    dict(item="tkep022", artist="Smooth Operator",
         names={"in_your_eyes": "In Your Eyes", "ontoi": "Ontoi"}),
    dict(item="Lav03_fosforo-jangala"),
    # micro.Dreams numbers its tracks with bare numerals ("I", "VII") -- useless
    # on a radio display and as a search term, so give them names
    dict(item="MNMN217", names={"01. I.mp3": "Dream I", "02. II.mp3": "Dream II",
                                "03. III.mp3": "Dream III", "04. IV.mp3": "Dream IV"}),
    dict(item="MNMN306", names={"03. VII.mp3": "Dream VII"}),
    # --- long-form: a 42-minute atmospheric DnB/jungle set -------------------
    dict(item="tkset011", artist="Rainforest",
         names={"Under_the_moon": "Under The Moon (42-minute session)"}),
    # --- Section27 comps, kept light (mixed hardness) ------------------------
    dict(item="s27-043WeAreOne-Section27Netlabel",
         only=["1-02Fracture", "1-15District", "3-06Rand6", "3-08RaymondScott"]),
    dict(item="s27-027Sectioned",
         only=["1-11Despoir", "2-09Nothing", "1-1310Tonnes", "2-13SobreMesa"]),
]

IMG_RE = re.compile(r"\.(jpe?g|png)$", re.I)


def get_json(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=45) as r:
        return json.load(r)


def secs(v: Any) -> float:
    try:
        if ":" in str(v):
            total = 0.0
            for part in str(v).split(":"):
                total = total * 60 + float(part)
            return total
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def find_ffmpeg() -> str | None:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return None


def decode_duration(url: str, ffmpeg: str | None) -> float:
    """Exact duration in seconds, by fully decoding the remote file.

    A header probe is not good enough: VBR files without a length header get
    an *estimate* from bitrate that can be off by seconds, and the station is
    clock-synced to these numbers. Decoding downloads the file (~5 MB), so
    this only runs for tracks archive.org couldn't measure reliably.
    """
    if not ffmpeg:
        return 0.0
    for attempt in range(VERIFY_ATTEMPTS):  # remote reads flake like any other
        try:
            out = subprocess.run(
                [ffmpeg, "-hide_banner", "-nostdin", "-i", url, "-vn", "-f", "null", "-"],
                capture_output=True, encoding="utf-8", errors="replace",
                timeout=300).stderr or ""  # not cp1252: ffmpeg prints arbitrary bytes
        except subprocess.TimeoutExpired:
            out = ""
        stamps = re.findall(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)", out)
        if stamps:
            h, m, s = stamps[-1]
            return int(h) * 3600 + int(m) * 60 + float(s)
        time.sleep(2 * (attempt + 1))
    return 0.0


def duration_is_plausible(length: float, size: Any) -> bool:
    """archive.org's length vs. file size: an MP3 lives between ~56 and ~330 kbps."""
    if length <= 0:
        return False
    try:
        kbps = int(size) * 8 / length / 1000
    except (TypeError, ValueError):
        return True  # no size to check against; trust the metadata
    return 56 <= kbps <= 330


def clean_title(name: str) -> str:
    base = re.sub(r"\.mp3$", "", os.path.basename(name), flags=re.I)
    base = re.sub(r"^[a-z]?\d{0,2}[\s._-]+", "", base)  # leading track number
    parts = [p for p in re.split(r"\s+-\s+|_-_", base) if p.strip()]
    return re.sub(r"[_]+", " ", parts[-1]).strip() if parts else base


def pick_cover(files: list[dict[str, Any]], item: str) -> str | None:
    best, best_score = None, -1
    for f in files:
        n = f["name"]
        if not IMG_RE.search(n) or "/" in n or "back" in n.lower():
            continue
        low = n.lower()
        score = 1
        if "cover" in low or "front" in low or "artwork" in low:
            score = 4
        elif low.startswith(item.lower()) or low.startswith("a-"):
            score = 3
        elif "thumb" in low:
            score = 0.5
        elif "large" in low:
            score = 2
        if score > best_score:
            best, best_score = n, score
    return f"{IA}/download/{item}/{urllib.parse.quote(best)}" if best else None


def pick_tracks(files: list[dict[str, Any]], spec: Spec) -> list[dict[str, Any]]:
    mp3 = [f for f in files if f["name"].lower().endswith(".mp3")]
    orig = [f for f in mp3 if f.get("source") == "original"]
    mp3 = sorted(orig or mp3, key=lambda f: f["name"])
    if spec.get("skip"):
        rx = re.compile(spec["skip"], re.I)
        mp3 = [f for f in mp3 if not rx.search(f["name"]) and not rx.search(f.get("title", ""))]
    if spec.get("only"):
        picked = []
        for needle in spec["only"]:
            hit = next((f for f in mp3 if needle.lower() in f["name"].lower()), None)
            if hit:
                picked.append(hit)
            else:
                print(f"  ! {spec['item']}: no file matching {needle!r}", file=sys.stderr)
        return picked
    take = spec.get("take")
    if take and take < len(mp3):
        idx = sorted({round(i * (len(mp3) - 1) / (take - 1)) for i in range(take)}) if take > 1 else [0]
        mp3 = [mp3[i] for i in idx]
    return mp3


def build_release(spec: Spec, ffmpeg: str | None) -> list[Track]:
    item = spec["item"]
    d = get_json(f"{IA}/metadata/{urllib.parse.quote(item)}")
    meta = d.get("metadata", {})
    lic = meta.get("licenseurl")
    if not lic or "creativecommons.org" not in lic:
        print(f"  ! {item}: no explicit CC license -- SKIPPED", file=sys.stderr)
        return []
    files = d.get("files", [])
    art = pick_cover(files, item)
    release = meta.get("title", item)
    creator = meta.get("creator")
    creator = ", ".join(creator) if isinstance(creator, list) else (creator or "")
    out = []
    for f in pick_tracks(files, spec):
        url = f"{IA}/download/{item}/{urllib.parse.quote(f['name'], safe='/')}"
        dur = secs(f.get("length"))
        if not duration_is_plausible(dur, f.get("size")):
            dur = decode_duration(url, ffmpeg)
        if dur <= 0:
            print(f"  ! {item}/{f['name']}: unknown duration -- dropped", file=sys.stderr)
            continue
        names = spec.get("names", {})
        override = next((v for k, v in names.items() if k.lower() in f["name"].lower()), None)
        out.append({
            "title": override or (f.get("title") or "").strip() or clean_title(f["name"]),
            "artist": (f.get("artist") or f.get("creator") or spec.get("artist") or creator).strip(),
            "dur": int(round(dur)),
            "url": url,
            "item": item,
            "release": release,
            "lic": lic,
            "art": art,
        })
    return out


def check_stream(track: Track) -> bool:
    """True if the stream answers with audio bytes and CORS headers.

    archive.org throws occasional transient resets under load, so retry with
    backoff before declaring a track dead -- a false negative silently thins
    the crate.
    """
    for attempt in range(VERIFY_ATTEMPTS):
        req = urllib.request.Request(track["url"], headers={"Range": "bytes=0-1"})
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                return bool(r.status in (200, 206) and r.headers.get("Access-Control-Allow-Origin"))
        except OSError:  # URLError, timeouts and connection resets all land here
            time.sleep(2 * (attempt + 1))
    return False


def norm(s: str) -> str:
    """Comparison key: lowercase, no accents, no (parentheticals), no punctuation."""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"\(.*?\)|\[.*?\]", " ", s.lower())
    s = re.sub(r"\b(feat|ft|featuring)\b.*$", " ", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def artist_matches(want: str, have: str) -> bool:
    return bool(want) and bool(have) and (want in have or have in want)


def apple_lookup(track: Track) -> str | None:
    """Apple Music URL if iTunes has this exact artist+title, else None.

    Raises OSError if the API itself is unavailable (so callers don't cache a
    network failure as "not on Apple Music").
    """
    want_artist, want_title = norm(track["artist"]), norm(track["title"])
    if not want_artist or not want_title:
        return None
    qs = urllib.parse.urlencode({
        "term": f"{track['artist']} {track['title']}", "entity": "song",
        "limit": 8, "country": "US"})
    for hit in get_json(f"https://itunes.apple.com/search?{qs}").get("results", []):
        if (artist_matches(want_artist, norm(hit.get("artistName", "")))
                and norm(hit.get("trackName", "")) == want_title and hit.get("trackViewUrl")):
            return hit["trackViewUrl"].split("?")[0]
    return None


def spotify_token() -> str | None:
    """App-only token (client-credentials flow), or None without credentials.

    Spotify's search API needs a free developer app. Credentials come from the
    environment -- never from the repo:
        SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET
    """
    cid, secret = os.environ.get("SPOTIFY_CLIENT_ID"), os.environ.get("SPOTIFY_CLIENT_SECRET")
    if not (cid and secret):
        return None
    basic = base64.b64encode(f"{cid}:{secret}".encode()).decode()
    req = urllib.request.Request(
        "https://accounts.spotify.com/api/token",
        data=urllib.parse.urlencode({"grant_type": "client_credentials"}).encode(),
        headers={"Authorization": f"Basic {basic}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["access_token"]


def make_spotify_lookup(token: str) -> Callable[[Track], str | None]:
    def lookup(track: Track) -> str | None:
        want_artist, want_title = norm(track["artist"]), norm(track["title"])
        if not want_artist or not want_title:
            return None
        qs = urllib.parse.urlencode({
            "q": f"track:{want_title} artist:{want_artist}", "type": "track", "limit": 8})
        req = urllib.request.Request(f"https://api.spotify.com/v1/search?{qs}",
                                     headers={"Authorization": f"Bearer {token}"})
        items: list[dict[str, Any]] = []
        for attempt in range(SPOTIFY_ATTEMPTS):
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    items = json.load(r).get("tracks", {}).get("items", [])
                break
            except urllib.error.HTTPError as e:
                if e.code != 429 or attempt == SPOTIFY_ATTEMPTS - 1:
                    raise
                time.sleep(int(e.headers.get("Retry-After", "5")) + 1)
        for hit in items:
            names = [norm(a["name"]) for a in hit.get("artists", [])]
            if (norm(hit.get("name", "")) == want_title
                    and any(artist_matches(want_artist, n) for n in names)):
                return hit.get("external_urls", {}).get("spotify")
        return None
    return lookup


def resolve_links(sched: list[Track], cache: dict[str, str | None],
                  lookup: Callable[[Track], str | None], field: str, delay: float) -> None:
    """Attach `field` links (in place) to tracks the lookup can find.

    Services rate-limit, so calls are spaced out; results (misses included)
    are cached by item+title; and an artist is abandoned after two misses --
    netlabel artists are mostly absent from the stores, and each miss costs
    `delay` seconds.
    """
    misses: dict[str, int] = {}
    for t in sched:
        key = f"{t['item']}|{t['title']}"
        if key not in cache:
            who = norm(t["artist"])
            if misses.get(who, 0) >= 2:
                continue  # don't cache: it's a shortcut, not an answer
            try:
                cache[key] = lookup(t)
            except OSError as e:
                print(f"  ! {field} lookup unavailable ({e}); leaving the rest unresolved",
                      file=sys.stderr)
                return
            time.sleep(delay)
            if cache[key] is None:
                misses[who] = misses.get(who, 0) + 1
        if cache.get(key):
            t[field] = cache[key]


def load_cache(path: str) -> dict[str, str | None]:
    if "--refresh-links" in sys.argv or not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def save_cache(path: str, cache: dict[str, str | None]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(cache, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")


def attach_streaming_links(sched: list[Track]) -> None:
    """Spotify first (the site's focus), then Apple Music; each cached."""
    token = None
    try:
        token = spotify_token()
    except OSError as e:
        print(f"  ! Spotify auth failed ({e}) -- check SPOTIFY_CLIENT_ID/SECRET", file=sys.stderr)
    services: list[tuple[str, str, Callable[[Track], str | None], float]] = []
    if token:
        services.append(("spotify", SPOTIFY_CACHE, make_spotify_lookup(token), SPOTIFY_DELAY_S))
    else:
        print("  (no Spotify credentials in env -- skipping Spotify; set SPOTIFY_CLIENT_ID "
              "and SPOTIFY_CLIENT_SECRET from a free developer.spotify.com app)")
    services.append(("apple", APPLE_CACHE, apple_lookup, APPLE_DELAY_S))
    for field, path, lookup, delay in services:
        print(f"resolving {field} links (cached; new lookups are rate-limited)...")
        cache = load_cache(path)
        try:
            resolve_links(sched, cache, lookup, field, delay)
        finally:  # keep partial progress if interrupted
            save_cache(path, cache)


def main() -> None:
    ffmpeg = find_ffmpeg()
    sched = []
    for spec in CRATE:
        print(f"{spec['item']}")
        try:
            sched.extend(build_release(spec, ffmpeg))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            print(f"  ! {spec['item']}: metadata fetch failed ({e}) -- SKIPPED", file=sys.stderr)

    print(f"verifying {len(sched)} streams...")
    with ThreadPoolExecutor(VERIFY_WORKERS) as pool:
        good = list(pool.map(check_stream, sched))
    dropped = [t for t, ok in zip(sched, good) if not ok]
    for t in dropped:
        print(f"  ! unreachable / no CORS: {t['url']}", file=sys.stderr)
    sched = [t for t, ok in zip(sched, good) if ok]

    if "--no-links" not in sys.argv:
        attach_streaming_links(sched)

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump({"epoch": EPOCH, "sched": sched}, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    hours = sum(t["dur"] for t in sched) / 3600
    on_spotify = sum(1 for t in sched if t.get("spotify"))
    on_apple = sum(1 for t in sched if t.get("apple"))
    print(f"wrote {OUT}: {len(sched)} tracks, {hours:.1f} h, "
          f"{len({t['item'] for t in sched})} releases, {len(dropped)} dropped, "
          f"{on_spotify} on Spotify, {on_apple} on Apple Music")


if __name__ == "__main__":
    main()
