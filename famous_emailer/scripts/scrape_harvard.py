#!/usr/bin/env python3
"""
Scrape Harvard Law faculty listing pages to extract names and profile URLs.

Example:
    python scripts/scrape_harvard.py --start-page 1 --max-pages 5 --output data/harvard_names.csv

This looks for <h3 class="faculty-feed__item-title"> elements on listing pages
and extracts the inner <a> text (name) and href (profile URL).
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
from typing import List, Tuple
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_LISTING_URL = "https://hls.harvard.edu/faculty/"


def fetch_listing_page(session: requests.Session, page: int) -> str:
    params = {"page": str(page), "faculty_type": "HLS Professors"}
    url = BASE_LISTING_URL
    resp = session.get(url, params=params, timeout=15)
    resp.raise_for_status()
    return resp.text


def parse_names_from_listing(html: str) -> List[Tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    items = soup.find_all("h3", class_="faculty-feed__item-title")
    results: List[Tuple[str, str]] = []
    for h3 in items:
        a = h3.find("a")
        if not a:
            continue
        name = a.get_text(strip=True)
        href = a.get("href")
        if not href:
            continue
        profile_url = urljoin(BASE_LISTING_URL, href)
        results.append((name, profile_url))
    return results


def write_csv(path: str, rows: List[Tuple[str, str]], source_page_template: str = "") -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["name", "profile_url", "source_url"])
        for name, profile_url, source_url in rows:
            writer.writerow([name, profile_url, source_url])


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description="Scrape Harvard Law faculty names and profile URLs")
    parser.add_argument("--start-page", type=int, default=1)
    parser.add_argument("--max-pages", type=int, default=10, help="max listing pages to try (will stop early if no results)")
    parser.add_argument("--delay", type=float, default=0.5, help="delay between page requests (seconds)")
    parser.add_argument("--output", default="data/harvard_names.csv")
    args = parser.parse_args(argv)

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
        }
    )

    seen_profiles = set()
    collected: List[Tuple[str, str, str]] = []

    for page in range(args.start_page, args.start_page + args.max_pages):
        try:
            html = fetch_listing_page(session, page)
        except Exception as exc:
            print(f"failed to fetch page {page}: {exc}", file=sys.stderr)
            break

        names = parse_names_from_listing(html)
        if not names:
            # assume we've exhausted listing pages
            print(f"no names found on page {page}; stopping", file=sys.stderr)
            break

        for name, profile_url in names:
            if profile_url in seen_profiles:
                continue
            seen_profiles.add(profile_url)
            source_url = f"{BASE_LISTING_URL}?page={page}&faculty_type=HLS%20Professors#content"
            collected.append((name, profile_url, source_url))

        print(f"page {page}: found {len(names)} names (total collected: {len(collected)})")
        time.sleep(args.delay)

    if not collected:
        print("no names collected", file=sys.stderr)
        return 2

    write_csv(args.output, collected)
    print(f"Wrote {len(collected)} rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))


