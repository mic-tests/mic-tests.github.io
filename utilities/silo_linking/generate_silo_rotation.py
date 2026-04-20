#!/usr/bin/env python3
"""
Monthly silo link rotation for mic-tests.github.io.
Patches HTML files in-place using comment markers:
  <!-- SILO_START:slot_a -->sentence with link<!-- SILO_END:slot_a -->

Run via GitHub Actions on the 1st of each month, or manually:
  python3 utilities/silo_linking/generate_silo_rotation.py
"""

import datetime
import hashlib
import html as html_lib
import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ---------------------------------------------------------------------------
# Silo links: which page → which slots → which target (anchor + URL)
# ---------------------------------------------------------------------------

SILO_LINKS = {
    "index.html": [
        {"slot": "slot_a", "anchor": "tone generator",          "url": "/tone-generator"},
    ],
    "tone-generator.html": [
        {"slot": "slot_a", "anchor": "mic test online",          "url": "/"},
        {"slot": "slot_b", "anchor": "headphone test",           "url": "/headphone-test"},
        {"slot": "slot_c", "anchor": "hearing test online",      "url": "/hearing-test"},
    ],
    "hearing-test.html": [
        {"slot": "slot_a", "anchor": "mic test online",          "url": "/"},
        {"slot": "slot_b", "anchor": "tone generator",           "url": "/tone-generator"},
        {"slot": "slot_c", "anchor": "audio latency test",       "url": "/audio-latency-test"},
        {"slot": "slot_d", "anchor": "sound level meter online", "url": "/sound-level-meter"},
    ],
    "audio-latency-test.html": [
        {"slot": "slot_a", "anchor": "mic test online",          "url": "/"},
        {"slot": "slot_b", "anchor": "hearing test online",      "url": "/hearing-test"},
        {"slot": "slot_c", "anchor": "online mic recorder",      "url": "/mic-recorder"},
    ],
    "headphone-test.html": [
        {"slot": "slot_a", "anchor": "tone generator",           "url": "/tone-generator"},
        {"slot": "slot_b", "anchor": "stereo test",              "url": "/stereo-test"},
    ],
    "stereo-test.html": [
        {"slot": "slot_a", "anchor": "tone generator",           "url": "/tone-generator"},
        {"slot": "slot_b", "anchor": "headphone test",           "url": "/headphone-test"},
        {"slot": "slot_c", "anchor": "bass test",                "url": "/bass-test"},
    ],
    "bass-test.html": [
        {"slot": "slot_a", "anchor": "tone generator",           "url": "/tone-generator"},
        {"slot": "slot_b", "anchor": "stereo test",              "url": "/stereo-test"},
        {"slot": "slot_c", "anchor": "speaker test online",      "url": "/speaker-volume-test"},
    ],
    "speaker-volume-test.html": [
        {"slot": "slot_a", "anchor": "tone generator",           "url": "/tone-generator"},
        {"slot": "slot_b", "anchor": "bass test",                "url": "/bass-test"},
        {"slot": "slot_c", "anchor": "what speakers do i have",  "url": "/show-speakers"},
    ],
    "show-speakers.html": [
        {"slot": "slot_a", "anchor": "tone generator",           "url": "/tone-generator"},
        {"slot": "slot_b", "anchor": "speaker test online",      "url": "/speaker-volume-test"},
        {"slot": "slot_c", "anchor": "sound level meter online", "url": "/sound-level-meter"},
    ],
    "sound-level-meter.html": [
        {"slot": "slot_a", "anchor": "hearing test online",      "url": "/hearing-test"},
        {"slot": "slot_b", "anchor": "voice frequency analyzer", "url": "/voice-frequency-analyzer"},
        {"slot": "slot_c", "anchor": "what speakers do i have",  "url": "/show-speakers"},
    ],
    "voice-frequency-analyzer.html": [
        {"slot": "slot_a", "anchor": "hearing test online",      "url": "/hearing-test"},
        {"slot": "slot_b", "anchor": "sound level meter online", "url": "/sound-level-meter"},
        {"slot": "slot_c", "anchor": "background noise analyzer","url": "/background-noise-analyzer"},
    ],
    "background-noise-analyzer.html": [
        {"slot": "slot_a", "anchor": "hearing test online",      "url": "/hearing-test"},
        {"slot": "slot_b", "anchor": "voice frequency analyzer", "url": "/voice-frequency-analyzer"},
        {"slot": "slot_c", "anchor": "online mic recorder",      "url": "/mic-recorder"},
    ],
    "mic-recorder.html": [
        {"slot": "slot_a", "anchor": "audio latency test",       "url": "/audio-latency-test"},
        {"slot": "slot_b", "anchor": "echo test",                "url": "/echo-test"},
        {"slot": "slot_c", "anchor": "background noise analyzer","url": "/background-noise-analyzer"},
    ],
    "echo-test.html": [
        {"slot": "slot_a", "anchor": "audio latency test",       "url": "/audio-latency-test"},
        {"slot": "slot_b", "anchor": "online mic recorder",      "url": "/mic-recorder"},
        {"slot": "slot_c", "anchor": "what microphone do i have","url": "/show-mic"},
    ],
    "show-mic.html": [
        {"slot": "slot_a", "anchor": "audio latency test",       "url": "/audio-latency-test"},
        {"slot": "slot_b", "anchor": "echo test",                "url": "/echo-test"},
    ],
}

# ---------------------------------------------------------------------------
# Injection targets: where to place each slot's marker on first run.
# (heading_tag, heading_text_fragment) — None = first <p> after <h1>.
# Uses partial text matching so minor entity differences don't break it.
# ---------------------------------------------------------------------------

INJECTION_TARGETS = {
    "index.html": {
        "slot_a": ("h1", None),
    },
    "tone-generator.html": {
        "slot_a": ("h1", None),
        "slot_b": ("h2", "What Is a Tone Generator?"),
        "slot_c": ("h3", "Hearing Range Assessment"),
    },
    "hearing-test.html": {
        "slot_a": ("h1", None),
        "slot_b": ("h2", "How to Take the Hearing Test"),
        "slot_c": ("h2", "Understanding Your Hearing Test Results"),
        "slot_d": ("h2", "Common Causes of High-Frequency Hearing Loss"),
    },
    "audio-latency-test.html": {
        "slot_a": ("h1", None),
        "slot_b": ("h2", "What Is Audio Latency?"),
        "slot_c": ("h2", "Audio Latency by Use Case"),
    },
    "headphone-test.html": {
        "slot_a": ("h1", None),
        "slot_b": ("h2", "What Does the Headphone Test Check?"),
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
    },
}

# ---------------------------------------------------------------------------
# Sentence templates — 6 per anchor keyword, {link} replaced at render time.
# ---------------------------------------------------------------------------

SENTENCES = {
    "mic test online": [
        "Run a {link} to confirm your microphone is working before your next call.",
        "A quick {link} catches input problems before they become meeting disasters.",
        "Use the free {link} to verify microphone levels and device details in seconds.",
        "The {link} checks your mic input, waveform, and device info in one step.",
        "Before any recording session, a {link} confirms your audio input is clean.",
        "The {link} runs entirely in your browser — no downloads or sign-up required.",
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
        "The {link} sweeps through 20Hz–200Hz to reveal your subwoofer's actual frequency floor.",
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
# Core helpers
# ---------------------------------------------------------------------------

def _strip_tags(s: str) -> str:
    return html_lib.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def pick_sentence(source_file: str, anchor: str, today: datetime.date) -> str:
    key = f"{today.year}-{today.month}-{source_file}-{anchor}"
    idx = int(hashlib.md5(key.encode()).hexdigest(), 16) % 6
    return SENTENCES[anchor][idx]


def make_sentence_html(template: str, url: str, anchor: str) -> str:
    link = f'<a href="{url}">{anchor}</a>'
    return template.replace("{link}", link)


def update_markers(html: str, slot: str, sentence_html: str) -> str:
    start = f"<!-- SILO_START:{slot} -->"
    end   = f"<!-- SILO_END:{slot} -->"
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.S)
    return pattern.sub(start + sentence_html + end, html)


def find_paragraph_end(html: str, heading_tag: str, heading_text: str | None) -> int | None:
    """Return position of </p> to inject before, based on the given heading."""
    if heading_text is None:
        # First <p> after the first </h1>
        m = re.search(r"</h1>", html)
        if not m:
            return None
        search_from = m.end()
    else:
        # Find heading tag whose stripped text contains heading_text fragment
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
        return html  # injection point not found — leave unchanged
    start = f"<!-- SILO_START:{slot} -->"
    end   = f"<!-- SILO_END:{slot} -->"
    injection = f" {start}{sentence_html}{end}"
    return html[:pos] + injection + html[pos:]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(today: datetime.date, dry_run: bool = False) -> None:
    errors: list[str] = []

    for page_file, links in SILO_LINKS.items():
        filepath = os.path.join(REPO_ROOT, page_file)
        if not os.path.exists(filepath):
            errors.append(f"MISSING FILE: {page_file}")
            continue

        html = open(filepath, encoding="utf-8").read()
        original = html

        for link_def in links:
            slot   = link_def["slot"]
            anchor = link_def["anchor"]
            url    = link_def["url"]

            sentence_html = make_sentence_html(
                pick_sentence(page_file, anchor, today), url, anchor
            )

            marker_start = f"<!-- SILO_START:{slot} -->"

            if marker_start in html:
                html = update_markers(html, slot, sentence_html)
            else:
                tag, text = INJECTION_TARGETS[page_file][slot]
                new_html = insert_markers(html, slot, sentence_html, tag, text)
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
    today   = datetime.date.today()
    print(f"Silo rotation — {today.year}-{today.month:02d}"
          + (" [DRY RUN]" if dry_run else ""))
    run(today, dry_run=dry_run)
    print("Done.")
