#!/usr/bin/env python3
"""
Scrape Columbia Law faculty listing pages to extract names, profile URLs, and mailto emails.

The script attempts to find a mailto link inside each listing item; if none is present,
it will fetch the profile page and look for mailto anchors there.

Usage:
    python scripts/scrape_columbia.py --start-page 1 --max-pages 5 --output data/columbia_names.csv
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
from typing import List, Tuple, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE_LISTING_URL = "https://www.law.columbia.edu/faculty-and-scholarship/all-faculty"


def fetch_page(session: requests.Session, page: int) -> str:
    params = {"page": str(page)}
    resp = session.get(BASE_LISTING_URL, params=params, timeout=15)
    resp.raise_for_status()
    return resp.text


def find_mailto_in_fragment(soup: BeautifulSoup) -> Optional[str]:
    a = soup.find("a", href=lambda h: h and h.lower().startswith("mailto:"))
    if not a:
        return None
    href = a.get("href") or ""
    return href.split("mailto:")[1].split("?")[0].strip() if "mailto:" in href else None


def parse_listing(html: str) -> List[Tuple[str, str, Optional[str]]]:
    """
    Returns a list of (name, profile_url, email_or_none)
    """
    soup = BeautifulSoup(html, "html.parser")
    results: List[Tuple[str, str, Optional[str]]] = []

    # Heuristic: find anchor links that look like profile links (contain '/faculty' or '/faculty-and-scholarship')
    anchors = soup.find_all("a", href=True)
    seen_profiles = set()
    for a in anchors:
        href = a.get("href")
        if not href:
            continue
        if "/faculty" not in href and "faculty-and-scholarship" not in href:
            continue
        text = a.get_text(strip=True)
        if not text or len(text) < 2:
            continue
        profile_url = urljoin(BASE_LISTING_URL, href)
        if profile_url in seen_profiles:
            continue
        seen_profiles.add(profile_url)

        # try to find a mailto within the same parent container
        parent = a.find_parent()
        email = None
        if parent:
            email = find_mailto_in_fragment(parent)

        results.append((text, profile_url, email))
    return results


def fetch_profile_for_mailto(session: requests.Session, profile_url: str) -> Optional[str]:
    try:
        resp = session.get(profile_url, timeout=15)
        resp.raise_for_status()
    except Exception:
        return None
    soup = BeautifulSoup(resp.text, "html.parser")
    return find_mailto_in_fragment(soup)


def write_csv(path: str, rows: List[Tuple[str, str, Optional[str]]]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["name", "profile_url", "email", "source_url"])
        for name, profile_url, email in rows:
            source_url = profile_url
            writer.writerow([name, profile_url, email or "", source_url])


def main(argv: List[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--start-page", type=int, default=1)
    p.add_argument("--max-pages", type=int, default=5)
    p.add_argument("--delay", type=float, default=0.5)
    p.add_argument("--output", default="data/columbia_names.csv")
    args = p.parse_args(argv)

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"})

    collected = []
    seen_profiles = set()

    for page in range(args.start_page, args.start_page + args.max_pages):
        try:
            html = fetch_page(session, page)
        except Exception as exc:
            print(f"failed to fetch listing page {page}: {exc}", file=sys.stderr)
            break

        entries = parse_listing(html)
        if not entries:
            print(f"no entries found on page {page}; stopping", file=sys.stderr)
            break

        for name, profile_url, email in entries:
            if profile_url in seen_profiles:
                continue
            seen_profiles.add(profile_url)
            if not email:
                # fetch profile page to try to find mailto
                email = fetch_profile_for_mailto(session, profile_url)
            collected.append((name, profile_url, email))

        print(f"page {page}: found {len(entries)} entries (collected {len(collected)})")
        time.sleep(args.delay)

    if not collected:
        print("no contacts collected", file=sys.stderr)
        return 2

    write_csv(args.output, collected)
    print(f"Wrote {len(collected)} rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))


