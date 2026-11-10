"""
google_ads_fetch_volumes_mictest.py
--------------------------------------
Fetches Google Ads keyword historical metrics for each tool page on the
mictest.dev (MicTest site).

Usage:
    python google_ads_fetch_volumes_mictest.py --customer-id XXXXXXXXXX
    python google_ads_fetch_volumes_mictest.py --customer-id XXXXXXXXXX --geo 2840
    python google_ads_fetch_volumes_mictest.py --dry-run
"""

import os
import sys
import time
import argparse
import logging
from datetime import datetime
from pathlib import Path

import openpyxl

SCRIPT_DIR = Path(__file__).parent
YAML_PATH = SCRIPT_DIR / "google-ads.yaml"
OUTPUT_DIR = SCRIPT_DIR / "output"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

RETRY_LIMIT = 3
RETRY_DELAY = 5

GEO_TARGETS = {
    "2840": "United States",
    "2356": "India",
    "2036": "Australia",
    "2826": "United Kingdom",
    "2124": "Canada",
}

LANGUAGE_EN = "languageConstants/1000"

# ── MicTest pages — one primary keyword per tool page ────────────────────────
# All 15 tool pages on mictest.dev (src/content/*.json). `keyword` is each page's primary keyword from the
# silo plan in CLAUDE.md; `cluster` is the silo it belongs to.
MICTEST_PAGES = [
    # Pillar
    {"name": "Mic Test Online",           "cluster": "Pillar",                              "slug": "index",                      "keyword": "mic test"},
    # Silo A -- Speaker & Headphone Testing
    {"name": "Tone Generator",            "cluster": "A. Speaker & Headphone (hub)",        "slug": "tone-generator",             "keyword": "tone generator"},
    {"name": "Headphone Test",            "cluster": "A. Speaker & Headphone",              "slug": "headphone-test",             "keyword": "headphone test"},
    {"name": "Stereo Test",               "cluster": "A. Speaker & Headphone",              "slug": "stereo-test",                "keyword": "stereo test"},
    {"name": "Bass Test",                 "cluster": "A. Speaker & Headphone",              "slug": "bass-test",                  "keyword": "bass test"},
    {"name": "Speaker Volume Test",       "cluster": "A. Speaker & Headphone",              "slug": "speaker-volume-test",        "keyword": "speaker test online"},
    {"name": "Show My Speakers",          "cluster": "A. Speaker & Headphone",              "slug": "show-speakers",              "keyword": "what speakers do i have"},
    # Silo B -- Hearing & Sound Analysis
    {"name": "Hearing Test Online",       "cluster": "B. Hearing & Sound Analysis (hub)",   "slug": "hearing-test",               "keyword": "hearing test online"},
    {"name": "Sound Level Meter Online",  "cluster": "B. Hearing & Sound Analysis",         "slug": "sound-level-meter",          "keyword": "sound level meter online"},
    {"name": "Voice Frequency Analyzer",  "cluster": "B. Hearing & Sound Analysis",         "slug": "voice-frequency-analyzer",   "keyword": "voice frequency analyzer"},
    {"name": "Background Noise Analyzer", "cluster": "B. Hearing & Sound Analysis",         "slug": "background-noise-analyzer",  "keyword": "background noise analyzer"},
    # Silo C -- Microphone Tools
    {"name": "Audio Latency Test",        "cluster": "C. Microphone Tools (hub)",           "slug": "audio-latency-test",         "keyword": "audio latency test"},
    {"name": "Online Mic Recorder",       "cluster": "C. Microphone Tools",                 "slug": "mic-recorder",               "keyword": "online mic recorder"},
    {"name": "Echo Test",                 "cluster": "C. Microphone Tools",                 "slug": "echo-test",                  "keyword": "echo test"},
    {"name": "Show My Mic",               "cluster": "C. Microphone Tools",                 "slug": "show-mic",                   "keyword": "what microphone do i have"},
]


def competition_label(value) -> str:
    mapping = {0: "UNSPECIFIED", 1: "UNKNOWN", 2: "LOW", 3: "MEDIUM", 4: "HIGH"}
    try:
        return mapping.get(int(value), str(value))
    except Exception:
        return str(value)


def fetch_metrics_batch(client, customer_id, keywords, geo_target_id):
    kp_idea_service = client.get_service("KeywordPlanIdeaService")
    request = client.get_type("GenerateKeywordHistoricalMetricsRequest")

    request.customer_id = customer_id
    request.language = LANGUAGE_EN
    if geo_target_id:
        request.geo_target_constants.append(
            client.get_service("GeoTargetConstantService")
            .geo_target_constant_path(geo_target_id)
        )
    request.keyword_plan_network = (
        client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH
    )
    request.keywords.extend(keywords)

    response = kp_idea_service.generate_keyword_historical_metrics(request=request)

    results = {}
    for result in response.results:
        kw = result.text.lower()
        m = result.keyword_metrics
        results[kw] = {
            "avg_monthly_searches": m.avg_monthly_searches,
            "competition":          competition_label(m.competition),
            "competition_index":    m.competition_index,
            "low_top_of_page_bid":  round(m.low_top_of_page_bid_micros / 1_000_000, 2)
                                    if m.low_top_of_page_bid_micros else None,
            "high_top_of_page_bid": round(m.high_top_of_page_bid_micros / 1_000_000, 2)
                                    if m.high_top_of_page_bid_micros else None,
        }
    return results


def fetch_all_metrics(client, customer_id, pages, geo_target_id):
    keywords_list = [p["keyword"] for p in pages]
    log.info(f"Fetching metrics for {len(keywords_list)} keywords…")

    for attempt in range(1, RETRY_LIMIT + 1):
        try:
            metrics_map = fetch_metrics_batch(client, customer_id, keywords_list, geo_target_id)
            break
        except Exception as e:
            if attempt < RETRY_LIMIT:
                log.warning(f"  Attempt {attempt} failed: {e} — retrying in {RETRY_DELAY}s…")
                time.sleep(RETRY_DELAY)
            else:
                log.error(f"  Failed after {RETRY_LIMIT} attempts: {e}")
                metrics_map = {}

    all_results = []
    for page in pages:
        m = metrics_map.get(page["keyword"].lower(), {})
        all_results.append({
            **page,
            "avg_monthly_searches": m.get("avg_monthly_searches"),
            "competition":          m.get("competition"),
            "competition_index":    m.get("competition_index"),
            "low_top_of_page_bid":  m.get("low_top_of_page_bid"),
            "high_top_of_page_bid": m.get("high_top_of_page_bid"),
        })
    return all_results


XLSX_FIELDS = [
    "name", "cluster", "slug", "keyword",
    "avg_monthly_searches", "competition", "competition_index",
    "low_top_of_page_bid", "high_top_of_page_bid",
]


def save_xlsx(rows, path):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "MicTest Search Volumes"
    ws.append(XLSX_FIELDS)
    for row in rows:
        ws.append([row.get(f) for f in XLSX_FIELDS])
    wb.save(path)
    log.info(f"Saved {len(rows)} rows → {path}")


def print_summary(rows):
    has_data = [r for r in rows if r.get("avg_monthly_searches") is not None]
    sorted_rows = sorted(has_data, key=lambda x: x["avg_monthly_searches"], reverse=True)

    print("\n" + "=" * 80)
    print("  MICTEST PAGES — SEARCH VOLUMES")
    print("=" * 80)
    print(f"  {'Page':<30} {'Keyword':<35} {'Volume':>8}  {'KD'}")
    print("-" * 80)
    for r in sorted_rows:
        print(f"  {r['name'][:30]:<30} {r['keyword'][:35]:<35} {r['avg_monthly_searches']:>8,}  {r['competition']}")
    print("=" * 80)

    no_data = [r for r in rows if r.get("avg_monthly_searches") is None]
    if no_data:
        print(f"\n  {len(no_data)} keywords returned no volume data (<10 searches/month)")
        for r in no_data:
            print(f"    - {r['keyword']}")
    print()


def parse_args():
    p = argparse.ArgumentParser(description="Fetch Google Ads search volumes for MicTest pages")
    p.add_argument("--customer-id", default=None,
                   help="Google Ads customer ID (digits only). "
                        "Can also be set via GOOGLE_ADS_CUSTOMER_ID env var.")
    p.add_argument("--geo", default=None,
                   help="Geo target ID (e.g. 2840=US, 2356=India). Omit for global.")
    p.add_argument("--dry-run", action="store_true",
                   help="Print keywords only, skip API call")
    p.add_argument("--yaml", default=str(YAML_PATH),
                   help="Path to google-ads.yaml credentials file")
    return p.parse_args()


def main():
    args = parse_args()

    customer_id = (
        args.customer_id
        or os.environ.get("GOOGLE_ADS_CUSTOMER_ID", "")
    ).replace("-", "").strip()

    pages = MICTEST_PAGES
    log.info(f"MicTest site: {len(pages)} keywords across {len(pages)} pages")

    if args.dry_run:
        print(f"\nDRY RUN — {len(pages)} keywords to be fetched:\n")
        for p in pages:
            print(f"  [{p['name']:<30}]  {p['keyword']}")
        return

    if not customer_id:
        log.error(
            "No customer ID provided. Pass --customer-id XXXXXXXXXX "
            "or set GOOGLE_ADS_CUSTOMER_ID environment variable."
        )
        sys.exit(1)

    try:
        from google.ads.googleads.client import GoogleAdsClient
    except ImportError:
        log.error("google-ads not installed. Run: pip install google-ads openpyxl")
        sys.exit(1)

    log.info(f"Connecting to Google Ads API (customer: {customer_id}, geo: {GEO_TARGETS.get(args.geo, args.geo) if args.geo else 'Global'})…")
    client = GoogleAdsClient.load_from_storage(args.yaml)

    start = time.time()
    results = fetch_all_metrics(client, customer_id, pages, args.geo)
    elapsed = time.time() - start
    log.info(f"Completed in {elapsed:.1f}s")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    geo_label = GEO_TARGETS.get(args.geo, args.geo).lower().replace(" ", "_") if args.geo else "global"
    out_path = OUTPUT_DIR / f"mictest_search_volumes_{geo_label}_{timestamp}.xlsx"
    save_xlsx(results, out_path)
    print_summary(results)


if __name__ == "__main__":
    main()
