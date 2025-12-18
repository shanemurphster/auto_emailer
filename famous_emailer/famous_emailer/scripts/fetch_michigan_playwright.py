#!/usr/bin/env python3
from __future__ import annotations

"""
Playwright-based fetcher for Michigan Law faculty profile pages.

Requirements:
  pip install playwright
  playwright install

Usage:
  python scripts/fetch_michigan_playwright.py --mapping data/michigan_name_slug_map.csv

Behavior:
  - Reads a CSV mapping `name,slug` or a names file + slugs file pair.
  - Opens each profile URL with Playwright, waits for load, and extracts the
    first `mailto:` link found on the page.
  - Writes a per-site CSV (`--out-site-csv`) and appends new contacts to
    `--append-to` (default `data/law_contacts.csv`).
"""

import argparse
import csv
import os
import time
from typing import Dict, List, Optional, Tuple

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


DEFAULT_BASE = "https://michigan.law.umich.edu/faculty-and-scholarship/our-faculty/"


def read_mapping_csv(path: str) -> List[Tuple[str, str]]:
    rows: List[Tuple[str, str]] = []
    with open(path, "r", encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        for rec in r:
            name = (rec.get("name") or "").strip()
            slug = (rec.get("slug") or "").strip()
            if name and slug:
                rows.append((name, slug))
    return rows


def append_contacts_to_csv(path: str, rows: List[Tuple[str, str, str, str]]) -> int:
    written = 0
    existing = set()
    try:
        with open(path, "r", encoding="utf-8", newline="") as rf:
            reader = csv.DictReader(rf)
            for r in reader:
                em = (r.get("email") or "").strip().lower()
                if em:
                    existing.add(em)
    except FileNotFoundError:
        # will create file
        pass

    need_header = not os.path.exists(path)
    with open(path, "a", encoding="utf-8", newline="") as wf:
        writer = csv.writer(wf)
        if need_header:
            writer.writerow(["name", "email", "affiliation", "source_url"])
        for name, email, aff, src in rows:
            key = (email or "").strip().lower()
            if not key or key in existing:
                continue
            writer.writerow([name or "", email, aff or "", src or ""])
            existing.add(key)
            written += 1
    return written


def extract_mailto_from_page(page) -> Optional[str]:
    # Look for any anchor with href starting mailto:
    anchors = page.query_selector_all('a[href^="mailto:"]')
    if anchors:
        href = anchors[0].get_attribute("href") or ""
        if href.startswith("mailto:"):
            return href.split(":", 1)[1].split("?", 1)[0].strip()
    return None


def main() -> None:
    p = argparse.ArgumentParser(description="Playwright fetcher for Michigan profile pages")
    p.add_argument("--mapping", help="CSV mapping file name->slug (preferred)", default="data/michigan_name_slug_map.csv")
    p.add_argument("--names-file", help="Fallback names file (newline)", default="michigan_names.txt")
    p.add_argument("--slugs-file", help="Fallback slugs file (one slug per line)", default="data/michigan_slugs.txt")
    p.add_argument("--base-url", help="Base profile URL", default=DEFAULT_BASE)
    p.add_argument("--out-site-csv", help="Per-site CSV output", default="data/michigan_contacts_playwright.csv")
    p.add_argument("--append-to", help="Global CSV to append to", default="data/law_contacts.csv")
    p.add_argument("--affiliation", help="Affiliation string", default="University of Michigan")
    p.add_argument("--headless", action="store_true", help="Run browser headless (recommended)")
    p.add_argument("--delay", type=float, default=0.8, help="Delay between profile visits (seconds)")
    args = p.parse_args()

    # Load mapping either from mapping CSV or fallback to names+slugs
    mapping: List[Tuple[str, str]] = []
    if os.path.exists(args.mapping):
        mapping = read_mapping_csv(args.mapping)
    else:
        # fallback: pair names and slugs
        if not os.path.exists(args.names_file) or not os.path.exists(args.slugs_file):
            raise SystemExit("Provide either mapping CSV or both names and slugs files.")
        with open(args.names_file, "r", encoding="utf-8") as nf, open(args.slugs_file, "r", encoding="utf-8") as sf:
            names = [l.strip() for l in nf.readlines() if l.strip()]
            slugs = [l.strip() for l in sf.readlines() if l.strip()]
        if len(names) != len(slugs):
            raise SystemExit("Names and slugs counts differ; please regenerate mapping.")
        mapping = list(zip(names, slugs))

    print(f"Loaded {len(mapping)} name->slug entries")

    results: List[Tuple[str, str, str, str]] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=args.headless)
        context = browser.new_context()
        page = context.new_page()
        for name, slug in mapping:
            profile_url = args.base_url.rstrip("/") + "/" + slug
            try:
                print(f"Visiting {profile_url}")
                page.goto(profile_url, timeout=30000)
                # wait for either a mailto to appear or network idle / small timeout
                try:
                    page.wait_for_selector('a[href^="mailto:"]', timeout=8000)
                except PlaywrightTimeoutError:
                    # Not found quickly; still attempt to extract after waiting a bit
                    pass
                email = extract_mailto_from_page(page)
                if email:
                    print(f"Found: {name} -> {email}")
                    results.append((name, email, args.affiliation, profile_url))
                else:
                    print(f"No email on page: {profile_url}")
            except PlaywrightTimeoutError as e:
                print(f"Timeout visiting {profile_url}: {e}")
            except Exception as e:
                print(f"Error visiting {profile_url}: {e}")
            time.sleep(args.delay)
        context.close()
        browser.close()

    # write per-site CSV
    if results:
        os.makedirs(os.path.dirname(args.out_site_csv) or ".", exist_ok=True)
        with open(args.out_site_csv, "w", encoding="utf-8", newline="") as cf:
            w = csv.writer(cf)
            w.writerow(["name", "email", "affiliation", "source_url"])
            for r in results:
                w.writerow(r)
        appended = append_contacts_to_csv(args.append_to, results)
        print(f"Wrote {len(results)} to {args.out_site_csv}; appended {appended} new contacts to {args.append_to}")
    else:
        print("No contacts found.")


if __name__ == "__main__":
    main()


