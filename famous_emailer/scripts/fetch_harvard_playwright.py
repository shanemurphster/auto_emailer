#!/usr/bin/env python3
"""
Playwright-based fetcher for Harvard Law profile pages.

Reads a mapping CSV (default: data/harvard_name_slug_map.csv) with columns:
  name,slug,profile_url,source_url

For each profile_url it opens the page in Playwright, looks for an <a href="mailto:..."> and
writes results to:
  - data/harvard_contacts_playwright.csv
  - appends new contacts to data/law_contacts.csv (skips duplicate emails)

Usage:
  pip install playwright
  playwright install
  python scripts/fetch_harvard_playwright.py --mapping data/harvard_name_slug_map.csv --headless
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from typing import List, Dict

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError


def read_mapping(path: str) -> List[Dict[str, str]]:
    rows = []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for r in reader:
            rows.append(r)
    return rows


def read_existing_emails(law_contacts_path: str) -> set:
    emails = set()
    if not os.path.exists(law_contacts_path):
        return emails
    with open(law_contacts_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for r in reader:
            email = (r.get("email") or "").strip().lower()
            if email:
                emails.add(email)
    return emails


def append_to_csv(path: str, rows: List[Dict[str, str]], fieldnames: List[str]) -> None:
    exists = os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        if not exists:
            writer.writeheader()
        for r in rows:
            writer.writerow(r)


def main(argv: List[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--mapping", default="data/harvard_name_slug_map.csv")
    p.add_argument("--output", default="data/harvard_contacts_playwright.csv")
    p.add_argument("--law-contacts", default="data/law_contacts.csv")
    p.add_argument("--headless", action="store_true", help="run browser headless")
    p.add_argument("--delay", type=float, default=0.5)
    args = p.parse_args(argv)

    rows = read_mapping(args.mapping)
    if not rows:
        print(f"no rows in mapping {args.mapping}", file=sys.stderr)
        return 2

    existing_emails = read_existing_emails(args.law_contacts)

    out_rows = []
    law_rows_to_append = []

    with sync_playwright() as p_handle:
        browser = p_handle.chromium.launch(headless=args.headless)
        context = browser.new_context()
        page = context.new_page()
        page.set_default_timeout(15000)

        for idx, r in enumerate(rows, start=1):
            name = r.get("name", "").strip()
            profile_url = r.get("profile_url", "").strip()
            source_url = r.get("source_url", "").strip() or profile_url
            if not profile_url:
                continue

            print(f"[{idx}/{len(rows)}] visiting {profile_url}")
            try:
                page.goto(profile_url)
                # small wait for dynamic content
                time.sleep(args.delay)
            except PWTimeoutError:
                print(f"timeout loading {profile_url}", file=sys.stderr)
                continue
            except Exception as exc:
                print(f"error loading {profile_url}: {exc}", file=sys.stderr)
                continue

            # look for mailto anchors
            try:
                anchors = page.query_selector_all('a[href^="mailto:"]')
            except Exception:
                anchors = []

            found_emails = []
            for a in anchors:
                href = a.get_attribute("href") or ""
                if href.startswith("mailto:"):
                    email = href.split("mailto:")[1].split("?")[0].strip()
                    if email:
                        found_emails.append(email)

            if not found_emails:
                print(f"no mailto found for {profile_url}")
                continue

            # dedupe and append
            for email in sorted(set(found_emails)):
                lower_email = email.lower()
                out_rows.append({"name": name, "email": email, "profile_url": profile_url, "source_url": source_url})
                if lower_email not in existing_emails:
                    existing_emails.add(lower_email)
                    law_rows_to_append.append({"name": name, "email": email, "profile_url": profile_url, "source_url": source_url, "source": "harvard_playwright"})

        browser.close()

    # write playwright-specific CSV
    if out_rows:
        append_to_csv(args.output, out_rows, ["name", "email", "profile_url", "source_url"])
        print(f"Wrote {len(out_rows)} rows to {args.output}")

    # append to global law_contacts.csv (skip duplicates)
    if law_rows_to_append:
        # ensure law_contacts has expected header: name,email,profile_url,source_url,source
        append_to_csv(args.law_contacts, law_rows_to_append, ["name", "email", "profile_url", "source_url", "source"])
        print(f"Appended {len(law_rows_to_append)} new contacts to {args.law_contacts}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))


