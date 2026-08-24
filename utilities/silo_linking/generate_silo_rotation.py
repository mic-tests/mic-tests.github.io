#!/usr/bin/env python3
"""
Monthly silo link rotation for mictest.dev.

Full rotation each month:
  - Pillar rotates which hub it links to (deterministic shuffle, pick index 0).
  - Each hub's "down" link rotates to whichever supporter is first in that
    silo's shuffled chain for the month.
  - Supporter prev/next/bridge links update to match the shuffled order.

HTML files are patched in-place using comment markers:
  <!-- SILO_START:slot_a -->sentence with link<!-- SILO_END:slot_a -->

Run via GitHub Actions on the 1st of each month, or manually:
  python3 utilities/silo_linking/generate_silo_rotation.py
  python3 utilities/silo_linking/generate_silo_rotation.py --dry-run
"""

import datetime
import hashlib
import html as html_lib
import os
import random
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ---------------------------------------------------------------------------
# Silo structure
# ---------------------------------------------------------------------------

HUBS = ["tone-generator.html", "hearing-test.html", "audio-latency-test.html"]

HUB_ANCHORS = {
    "tone-generator.html":     "tone generator",
    "hearing-test.html":       "hearing test online",
    "audio-latency-test.html": "audio latency test",
}
HUB_URLS = {
    "tone-generator.html":     "/tone-generator",
    "hearing-test.html":       "/hearing-test",
    "audio-latency-test.html": "/audio-latency-test",
}

# Supporter pages in each silo. "anchor" = keyword used when linking TO this page.
SILO_SUPPORTERS = {
    "tone-generator.html": [        # Silo A — 5 pages
        {"file": "headphone-test.html",      "anchor": "headphone test",         "url": "/headphone-test"},
        {"file": "stereo-test.html",          "anchor": "stereo test",            "url": "/stereo-test"},
        {"file": "bass-test.html",            "anchor": "bass test",              "url": "/bass-test"},
        {"file": "speaker-volume-test.html",  "anchor": "speaker test online",    "url": "/speaker-volume-test"},
        {"file": "show-speakers.html",        "anchor": "what speakers do i have","url": "/show-speakers"},
    ],
    "hearing-test.html": [          # Silo B — 3 pages
        {"file": "sound-level-meter.html",         "anchor": "sound level meter online", "url": "/sound-level-meter"},
        {"file": "voice-frequency-analyzer.html",  "anchor": "voice frequency analyzer", "url": "/voice-frequency-analyzer"},
        {"file": "background-noise-analyzer.html", "anchor": "background noise analyzer","url": "/background-noise-analyzer"},
    ],
    "audio-latency-test.html": [    # Silo C — 3 pages
        {"file": "mic-recorder.html", "anchor": "online mic recorder",       "url": "/mic-recorder"},
        {"file": "echo-test.html",    "anchor": "echo test",                 "url": "/echo-test"},
        {"file": "show-mic.html",     "anchor": "what microphone do i have", "url": "/show-mic"},
    ],
}

# ---------------------------------------------------------------------------
# Injection targets: physical HTML location for each slot (first run only).
# (heading_tag, heading_text_fragment) — None = first <p> after <h1>.
# ---------------------------------------------------------------------------

INJECTION_TARGETS = {
    "index.html": {
        "slot_a": ("h1", None),
    },
    "tone-generator.html": {
        "slot_a": ("h1", None),
        "slot_b": ("h2", "What Is a Tone Generator?"),        # left hub (or empty)
        "slot_c": ("h3", "Hearing Range Assessment"),          # right hub (or empty)
        "slot_d": ("h3", "Tinnitus Frequency Matching"),       # down to first supporter
    },
    "hearing-test.html": {
        "slot_a": ("h1", None),
        "slot_b": ("h2", "How to Take the Hearing Test"),      # left hub (or empty)
        "slot_c": ("h2", "Understanding Your Hearing Test Results"),  # right hub (or empty)
        "slot_d": ("h2", "Common Causes of High-Frequency Hearing Loss"),  # down to first supporter
    },
    "audio-latency-test.html": {
        "slot_a": ("h1", None),
        "slot_b": ("h2", "What Is Audio Latency?"),            # left hub (or empty)
        "slot_c": ("h2", "Audio Latency by Use Case"),         # right hub (or empty)
        "slot_d": ("h2", "How to Reduce Audio Latency"),       # down to first supporter
    },
    "headphone-test.html": {
        "slot_a": ("h1", None),
        "slot_b": ("h2", "What Does the Headphone Test Check?"),
        "slot_c": ("h3", "Sound Coming from the Wrong Ear"),
    },
    "stereo-test.html": {
        "slot_a": ("h1", None),
        "slot_b": ("h2", "What Is Stereo Sound?"),
        "slot_c": ("h3", "Reversed Channels (Left/Right Swapped)"),
    },
    "bass-test.html": {
        "slot_a": ("h1", None),
        "slot_b": ("h2", "Understanding Bass Frequency Ranges"),
        "slot_c": ("h3", "No Bass Response at Low Frequencies"),
    },
    "speaker-volume-test.html": {
        "slot_a": ("h1", None),
        "slot_b": ("h3", "Speaker Channel Test"),
        "slot_c": ("h3", "Low Volume Speaker Test"),
    },
    "show-speakers.html": {
        "slot_a": ("h1", None),
        "slot_b": ("h2", "How to Find Out What Speakers You Have"),
        "slot_c": ("h3", "Device Name and Group ID"),
    },
    "sound-level-meter.html": {
        "slot_a": ("h1", None),
        "slot_b": ("h2", "What Is a Decibel?"),
        "slot_c": ("h2", "Sound Level Guide"),
    },
    "voice-frequency-analyzer.html": {
        "slot_a": ("h1", None),
        "slot_b": ("h3", "Fundamental Frequency"),
        "slot_c": ("h3", "Checking Microphone Frequency Response on Calls"),
    },
    "background-noise-analyzer.html": {
        "slot_a": ("h1", None),
        "slot_b": ("h3", "What Causes Noise in Each Frequency Band"),
        "slot_c": ("h3", "Low-Frequency Noise: HVAC"),
    },
    "mic-recorder.html": {
        "slot_a": ("h1", None),
        "slot_b": ("h2", "What Is an Online Mic Recorder"),
        "slot_c": ("h2", "Online Mic Recorder Privacy"),
    },
    "echo-test.html": {
        "slot_a": ("h1", None),
        "slot_b": ("h2", "Understanding Audio Echo"),
        "slot_c": ("h3", "Acoustic Echo"),
    },
    "show-mic.html": {
        "slot_a": ("h1", None),
        "slot_b": ("h2", "How to Find Out What Microphone You Have"),
        "slot_c": ("h3", "Device Name \u2014 What Microphone Do I Have?"),
    },
}

# ---------------------------------------------------------------------------
# Sentence templates — 6 per anchor keyword, {link} replaced at render time.
# ---------------------------------------------------------------------------

# Long-tail anchor variants used for the hub → pillar (slot_a) link.
# Rotated monthly per hub page so each hub uses a different variant.
HUB_UP_ANCHORS = [
    "mic test online",
    "online microphone test",
    "free microphone test",
    "test my microphone",
    "microphone test online",
    "mic check online",
]


def pick_hub_up_anchor(hub_file: str, today: datetime.date) -> str:
    key = f"{today.year}-M{today.month:02d}-{hub_file}-slot_a"
    idx = int(hashlib.md5(key.encode()).hexdigest(), 16) % len(HUB_UP_ANCHORS)
    return HUB_UP_ANCHORS[idx]


SENTENCES = {
    "mic test online": [
        "Run a {link} to confirm your microphone is working before your next call.",
        "A quick {link} catches input problems before they become meeting disasters.",
        "Use the free {link} to verify microphone levels and device details in seconds.",
        "The {link} checks your mic input, waveform, and device info in one step.",
        "Before any recording session, a {link} confirms your audio input is clean.",
        "The {link} runs entirely in your browser — no downloads or sign-up required.",
    ],
    "online microphone test": [
        "Run an {link} to verify your mic is working before any call or recording.",
        "The free {link} shows your waveform, levels, and device details in seconds.",
        "An {link} confirms your input is clean without any software to install.",
        "Use an {link} to diagnose why your microphone isn't picking up sound.",
        "An {link} checks your mic input, sample rate, and channel config in one step.",
        "Before a podcast or meeting, a quick {link} rules out hardware issues instantly.",
    ],
    "free microphone test": [
        "Run a {link} in your browser — no download or sign-up required.",
        "The {link} shows a live waveform and confirms your input is clean in seconds.",
        "A {link} catches mic faults before they turn into recording problems.",
        "Use the {link} to see your volume level, sample rate, and device name instantly.",
        "The {link} works with any browser-accessible microphone and runs entirely locally.",
        "Before any call or recording session, a {link} verifies your mic is ready.",
    ],
    "test my microphone": [
        "If you need to {link} quickly, the tool runs in your browser with one click.",
        "Use this page to {link} — it shows waveform, levels, and device info in real time.",
        "The fastest way to {link} is to open this page and speak a few words.",
        "To {link} before a call, click Start and watch the waveform respond to your voice.",
        "You can {link} without any downloads — the tool uses your browser's audio API directly.",
        "This tool lets you {link} and get instant feedback on volume, quality, and device details.",
    ],
    "microphone test online": [
        "Use this {link} to confirm your mic is picking up audio before your next call.",
        "A {link} shows your input waveform, volume level, and device specs in one place.",
        "The {link} runs entirely in the browser — no app or plugin required.",
        "Before recording, a {link} confirms your mic levels are clean and consistent.",
        "The {link} checks input quality and surfaces any device or permission issues instantly.",
        "A {link} is the fastest way to rule out hardware problems before a session.",
    ],
    "mic check online": [
        "Do a quick {link} before your next call to confirm your audio is working.",
        "The {link} shows a live waveform and volume reading as soon as you speak.",
        "A fast {link} catches input problems before they interrupt a live call.",
        "Use the {link} to verify your microphone, check levels, and confirm device details.",
        "The free {link} runs in your browser with no software or account required.",
        "Before any recording session, a {link} confirms your mic is clean and at the right level.",
    ],
    "tone generator": [
        "Use the {link} to sweep through frequencies and check your speaker response.",
        "A {link} lets you play any frequency from 20Hz to 20kHz directly in your browser.",
        "Test your speakers with a {link} — play sine waves, noise, or preset musical notes.",
        "The free {link} is the fastest way to check if your speakers reproduce bass and treble accurately.",
        "For speaker calibration or tinnitus matching, the {link} gives you precise frequency control.",
        "Run a {link} to expose frequency roll-off, driver distortion, or dead speaker channels.",
    ],
    "hearing test online": [
        "Check your full audible range with a {link} — from 20Hz bass to 20kHz treble.",
        "A {link} plays tones across the spectrum to show exactly where your hearing drops off.",
        "The free {link} takes under two minutes and runs entirely in your browser.",
        "Find your personal hearing limit with a {link} — no audiologist appointment needed.",
        "A {link} reveals high-frequency loss before it becomes noticeable in conversation.",
        "Use the {link} to compare hearing sensitivity across frequencies and track changes over time.",
    ],
    "audio latency test": [
        "Measure your system's round-trip delay with an {link}.",
        "The {link} quantifies microphone delay in milliseconds so you can diagnose recording drift.",
        "An {link} shows whether your setup introduces noticeable lag for recording or live use.",
        "Run an {link} to confirm your audio chain meets latency requirements for live performance.",
        "The {link} measures the gap between sound input and output — critical for podcasters and musicians.",
        "Use the {link} to pinpoint driver or buffer issues causing delay in your recordings.",
    ],
    "headphone test": [
        "Use the {link} to confirm both ear channels are balanced and undamaged.",
        "The {link} plays tones through each ear independently to catch driver faults early.",
        "A {link} reveals reversed channels, silent drivers, or uneven volume between ears.",
        "Run the {link} whenever audio sounds off-balance or one side seems quieter.",
        "The free {link} takes under a minute and works with any wired or Bluetooth headphones.",
        "Before a long listening session, a quick {link} confirms both channels are performing correctly.",
    ],
    "stereo test": [
        "Use the {link} to verify your left and right channels are correctly separated.",
        "The {link} plays audio through each channel independently to catch balance and routing issues.",
        "A {link} confirms your speakers are delivering true stereo rather than summed mono.",
        "Run a {link} if your audio sounds flat or identical in both ears.",
        "The free {link} detects reversed channels, mono collapse, and uneven output in seconds.",
        "For any stereo setup, the {link} is the quickest way to verify channel separation.",
    ],
    "bass test": [
        "Use the {link} to find out how deep your speakers can reproduce low frequencies.",
        "The {link} sweeps through 20Hz\u2013200Hz to reveal your subwoofer's actual frequency floor.",
        "Run a {link} to check whether your speakers handle sub-bass or roll off above 60Hz.",
        "A {link} exposes port resonance, driver rattle, or missing low end in any speaker setup.",
        "The free {link} plays every bass frequency so you can hear exactly where your system drops out.",
        "For subwoofer calibration, the {link} gives you precise low-frequency control.",
    ],
    "speaker test online": [
        "Verify your speakers are outputting correctly at every level with a {link}.",
        "The {link} plays tones at preset volume levels to check audio output consistency.",
        "Use the {link} to confirm your speakers respond correctly from low to maximum volume.",
        "A {link} detects clipping, distortion, or silent channels at different playback levels.",
        "Run a {link} to check whether your audio output is balanced and consistent.",
        "The free {link} works with any speakers or audio output device connected to your browser.",
    ],
    "what speakers do i have": [
        "If you need to know {link}, the browser's audio API lists every connected output device.",
        "Uncertain about {link}? The tool reads your system's audio output devices directly from the browser.",
        "For the answer to {link}, check your browser's audio output device list.",
        "The tool tells you {link} — along with sample rate, channel count, and device type.",
        "Find out {link} instantly — no system menus or driver software required.",
        "To see {link}, the browser's MediaDevices API identifies every output endpoint in seconds.",
    ],
    "sound level meter online": [
        "Measure your room's ambient noise in real time with a {link}.",
        "The {link} uses your microphone to display decibel levels as you speak or move.",
        "Use a {link} to check whether your recording environment is quiet enough for clean audio.",
        "A {link} shows current, average, and peak dB readings to help you optimise your setup.",
        "The free {link} runs in your browser and gives NIOSH-referenced safe exposure guidance.",
        "Before any recording session, a {link} confirms your ambient noise floor is within acceptable limits.",
    ],
    "voice frequency analyzer": [
        "See the live frequency spectrum of your voice with a {link}.",
        "The {link} displays your fundamental pitch, harmonics, and spectral distribution in real time.",
        "Use a {link} to check whether your voice is captured across its full frequency range.",
        "A {link} reveals thin, muffled, or over-processed audio by showing which frequencies are present.",
        "The free {link} is useful for vocal training, call quality checks, and microphone assessment.",
        "For a detailed look at your voice's spectral character, the {link} updates live as you speak.",
    ],
    "background noise analyzer": [
        "Measure what your microphone picks up when you're not talking with a {link}.",
        "The {link} breaks ambient sound into frequency bands to pinpoint fan hum or electrical interference.",
        "Use a {link} to check your recording environment before a session.",
        "A {link} shows whether your noise floor is within acceptable limits for podcast or voiceover work.",
        "The free {link} identifies specific noise sources — fan hum, mains hum, and reflections — by frequency.",
        "Run a {link} to see whether your microphone is picking up unwanted low-frequency rumble.",
    ],
    "online mic recorder": [
        "Record your voice directly in the browser with the {link} and download as MP3 or WAV.",
        "The {link} captures audio from your microphone with no upload and no account required.",
        "Use the {link} to make a quick test recording before an important call or session.",
        "The {link} runs locally in your browser — your audio is never sent to any server.",
        "For a fast, private voice memo, the {link} saves your recording directly to your device.",
        "The free {link} supports both MP3 and WAV output and works with any browser-accessible microphone.",
    ],
    "echo test": [
        "Check for audio feedback and delay with the free {link}.",
        "The {link} routes your microphone input back through your speakers so you can hear how you sound.",
        "Use the {link} to diagnose acoustic echo, electronic loopback, or network-introduced delay.",
        "A quick {link} reveals echo problems before they affect a live call or recording.",
        "The {link} simulates call conditions so you can hear and fix echo issues before others do.",
        "Run an {link} to confirm your echo cancellation settings are working correctly.",
    ],
    "what microphone do i have": [
        "If you need to know {link}, the browser's audio input API has the answer.",
        "Uncertain about {link}? Check your microphone name, specs, and settings directly in your browser.",
        "For the answer to {link}, the tool reads your audio input devices without any software.",
        "The tool tells you {link} — including device name, sample rate, and audio processing settings.",
        "Find out {link} in seconds — no driver software or system settings required.",
        "To confirm {link}, the browser's MediaDevices API identifies every connected input device.",
    ],
}

# ---------------------------------------------------------------------------
# Rotation helpers
# ---------------------------------------------------------------------------

def monthly_shuffle(items: list, seed_key: str, today: datetime.date) -> list:
    seed = int(hashlib.md5(f"{today.year}-M{today.month:02d}-{seed_key}".encode()).hexdigest(), 16)
    items = list(items)
    random.Random(seed).shuffle(items)
    return items


def pick_sentence(source_file: str, anchor: str, today: datetime.date) -> str:
    key = f"{today.year}-M{today.month:02d}-{source_file}-{anchor}"
    idx = int(hashlib.md5(key.encode()).hexdigest(), 16) % 6
    return SENTENCES[anchor][idx]


def generate_silo_links(today: datetime.date) -> dict:
    """Return SILO_LINKS dict for the given month via deterministic shuffle.

    Hub slot convention (all 3 hubs share identical slot semantics):
      slot_a = up to pillar ("mic test online" — fixed)
      slot_b = LEFT hub neighbour (None/empty if this hub is first in shuffled order)
      slot_c = RIGHT hub neighbour (None/empty if this hub is last in shuffled order)
      slot_d = DOWN to first supporter in this hub's shuffled chain (rotates monthly)
    """

    shuffled_hubs = monthly_shuffle(HUBS, "pillar", today)
    pillar_hub    = shuffled_hubs[0]  # pillar links to whichever hub is first this month

    silo_supporters = {
        hub: monthly_shuffle(SILO_SUPPORTERS[hub], f"silo_{i}", today)
        for i, hub in enumerate(HUBS)
    }

    links: dict = {}

    # --- Pillar: 1 outgoing link to whichever hub is first this month ---
    links["index.html"] = [
        {"slot": "slot_a", "anchor": HUB_ANCHORS[pillar_hub], "url": HUB_URLS[pillar_hub]},
    ]

    # --- Hub pages: slot_b=left, slot_c=right, slot_d=down (all rotate monthly) ---
    for pos, hub_file in enumerate(shuffled_hubs):
        is_first_hub = (pos == 0)
        is_last_hub  = (pos == len(shuffled_hubs) - 1)
        supporters   = silo_supporters[hub_file]
        left_hub     = shuffled_hubs[pos - 1] if not is_first_hub else None
        right_hub    = shuffled_hubs[pos + 1] if not is_last_hub  else None

        links[hub_file] = [
            {"slot": "slot_a", "anchor": pick_hub_up_anchor(hub_file, today), "url": "/"},
            {"slot": "slot_b",
             "anchor": HUB_ANCHORS[left_hub]  if left_hub  else None,
             "url":    HUB_URLS[left_hub]     if left_hub  else None},
            {"slot": "slot_c",
             "anchor": HUB_ANCHORS[right_hub] if right_hub else None,
             "url":    HUB_URLS[right_hub]    if right_hub else None},
            {"slot": "slot_d",
             "anchor": supporters[0]["anchor"], "url": supporters[0]["url"]},
        ]

    # Pull per-silo shuffled lists for use in the supporter section below
    silo_a = silo_supporters["tone-generator.html"]
    silo_b = silo_supporters["hearing-test.html"]
    silo_c = silo_supporters["audio-latency-test.html"]

    # --- Supporter pages ---
    silos = [
        ("tone-generator.html",     silo_a, 0),  # Silo A
        ("hearing-test.html",       silo_b, 1),  # Silo B
        ("audio-latency-test.html", silo_c, 2),  # Silo C
    ]

    for hub_file, supporters, silo_idx in silos:
        n          = len(supporters)
        hub_anchor = HUB_ANCHORS[hub_file]
        hub_url    = HUB_URLS[hub_file]

        for i, page in enumerate(supporters):
            is_first = (i == 0)
            is_last  = (i == n - 1)

            slot_a_def = {"slot": "slot_a", "anchor": hub_anchor, "url": hub_url}

            if is_first:
                next_page  = supporters[1]
                slot_b_def = {"slot": "slot_b",
                              "anchor": next_page["anchor"], "url": next_page["url"]}

                if silo_idx == 0:
                    # Silo A first — no backward bridge (A is the first silo)
                    slot_c_def = {"slot": "slot_c", "anchor": None, "url": None}
                else:
                    # Backward bridge: link to last of the previous silo
                    prev_silo  = [silo_a, silo_b][silo_idx - 1]
                    last_prev  = prev_silo[-1]
                    slot_c_def = {"slot": "slot_c",
                                  "anchor": last_prev["anchor"], "url": last_prev["url"]}

            elif is_last:
                prev_page  = supporters[i - 1]
                slot_b_def = {"slot": "slot_b",
                              "anchor": prev_page["anchor"], "url": prev_page["url"]}

                if silo_idx == 2:
                    # Silo C last — no forward bridge (C is the last silo)
                    slot_c_def = {"slot": "slot_c", "anchor": None, "url": None}
                else:
                    # Forward bridge: link to first of the next silo
                    next_silo  = [silo_b, silo_c][silo_idx]
                    first_next = next_silo[0]
                    slot_c_def = {"slot": "slot_c",
                                  "anchor": first_next["anchor"], "url": first_next["url"]}

            else:
                # Middle of chain
                prev_page  = supporters[i - 1]
                next_page  = supporters[i + 1]
                slot_b_def = {"slot": "slot_b",
                              "anchor": prev_page["anchor"], "url": prev_page["url"]}
                slot_c_def = {"slot": "slot_c",
                              "anchor": next_page["anchor"], "url": next_page["url"]}

            links[page["file"]] = [slot_a_def, slot_b_def, slot_c_def]

    return links

# ---------------------------------------------------------------------------
# Core HTML helpers
# ---------------------------------------------------------------------------

def _strip_tags(s: str) -> str:
    return html_lib.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def make_sentence_html(template: str, url: str, anchor: str) -> str:
    link = f'<a href="{url}">{anchor}</a>'
    return template.replace("{link}", link)


def update_markers(html: str, slot: str, sentence_html: str) -> str:
    start   = f"<!-- SILO_START:{slot} -->"
    end     = f"<!-- SILO_END:{slot} -->"
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.S)
    return pattern.sub(start + sentence_html + end, html)


def find_paragraph_end(html: str, heading_tag: str, heading_text: str | None) -> int | None:
    """Return position just before </p> to inject into, based on the given heading."""
    if heading_text is None:
        m = re.search(r"</h1>", html)
        if not m:
            return None
        search_from = m.end()
    else:
        for m in re.finditer(
            r"<" + heading_tag + r"[^>]*>(.*?)</" + heading_tag + r">",
            html, re.S
        ):
            if heading_text in _strip_tags(m.group(1)):
                search_from = m.end()
                break
        else:
            return None

    p_end = re.search(r"</p>", html[search_from:])
    if not p_end:
        return None
    return search_from + p_end.start()


def insert_markers(html: str, slot: str, sentence_html: str,
                   heading_tag: str, heading_text: str | None) -> str:
    pos = find_paragraph_end(html, heading_tag, heading_text)
    if pos is None:
        return html
    start     = f"<!-- SILO_START:{slot} -->"
    end       = f"<!-- SILO_END:{slot} -->"
    injection = f" {start}{sentence_html}{end}"
    return html[:pos] + injection + html[pos:]

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(today: datetime.date, dry_run: bool = False) -> None:
    silo_links = generate_silo_links(today)
    errors: list[str] = []

    for page_file, link_defs in silo_links.items():
        filepath = os.path.join(REPO_ROOT, page_file)
        if not os.path.exists(filepath):
            errors.append(f"MISSING FILE: {page_file}")
            continue

        html     = open(filepath, encoding="utf-8").read()
        original = html

        for link_def in link_defs:
            slot   = link_def["slot"]
            anchor = link_def["anchor"]
            url    = link_def["url"]

            marker_start = f"<!-- SILO_START:{slot} -->"

            if anchor is None:
                # Empty slot — clear any existing content, or insert empty markers
                if marker_start in html:
                    html = update_markers(html, slot, "")
                else:
                    tag, text = INJECTION_TARGETS[page_file][slot]
                    html = insert_markers(html, slot, "", tag, text)
            else:
                sentence_html = make_sentence_html(
                    pick_sentence(page_file, anchor, today), url, anchor
                )
                if marker_start in html:
                    html = update_markers(html, slot, sentence_html)
                else:
                    tag, text = INJECTION_TARGETS[page_file][slot]
                    new_html  = insert_markers(html, slot, sentence_html, tag, text)
                    if new_html == html:
                        errors.append(f"INJECT FAILED: {page_file}/{slot} — heading not found")
                    html = new_html

        if html != original:
            if dry_run:
                print(f"[dry-run] would update: {page_file}")
            else:
                open(filepath, "w", encoding="utf-8").write(html)
                print(f"Updated: {page_file}")
        else:
            print(f"No change: {page_file}")

    if errors:
        print("\nErrors:", file=sys.stderr)
        for e in errors:
            print(f"  {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv

    # Optional --date YYYY-MM override (useful for testing or backfilling)
    today = datetime.date.today()
    for arg in sys.argv[1:]:
        if arg.startswith("--date=") or (arg == "--date" and sys.argv.index(arg) + 1 < len(sys.argv)):
            raw = arg.split("=", 1)[1] if "=" in arg else sys.argv[sys.argv.index(arg) + 1]
            try:
                year, month = map(int, raw.split("-"))
                today = datetime.date(year, month, 1)
            except ValueError:
                print(f"Invalid --date value {raw!r}. Expected YYYY-MM.", file=sys.stderr)
                sys.exit(1)

    print(f"Silo rotation — {today.year}-M{today.month:02d}"
          + (" [DRY RUN]" if dry_run else ""))
    run(today, dry_run=dry_run)
    print("Done.")
