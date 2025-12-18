#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import re
import time
from typing import Iterable, List, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup

NAME_SELECTOR = ".node-title.h5.heading-with-line-small span"
DIRECTORY_URL_DEFAULT = "https://michigan.law.umich.edu/faculty-and-scholarship/our-faculty"
PROFILE_BASE_PATH = "/faculty-and-scholarship/our-faculty/"


def fetch_html(url: str, delay: float = 0.8) -> str:
    """
    Fetch HTML using a requests Session with a browser-like User-Agent and
    retry/backoff behavior.

    Rationale:
    Many university sites block non-browser User-Agents or throttle simple
    script requests, returning HTTP 403. Using a session with common
    browser headers and a small retry policy reduces 403/temporary failures
    while still behaving politely (we keep a small delay between requests).
    """
    time.sleep(delay)

    session = requests.Session()
    # Browser-like headers to avoid trivial bot blocks (sites returning 403)
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.google.com/",
        }
    )
    # Retry strategy for transient network/server issues
    retry_strategy = Retry(
        total=3,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"],
        backoff_factor=0.5,
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    resp = session.get(url, timeout=15)
    resp.raise_for_status()
    return resp.text


def slugify(name: str) -> str:
    s = name.strip().lower()
    # replace non-alphanumeric with dash
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-{2,}", "-", s)
    s = s.strip("-")
    return s


def parse_directory_names(html: str) -> List[str]:
    soup = BeautifulSoup(html, "lxml")
    els = soup.select(NAME_SELECTOR)
    names: List[str] = []
    for e in els:
        txt = (e.get_text(" ", strip=True) or "").strip()
        if txt:
            names.append(txt)
    # dedupe while preserving order
    seen = set()
    out = []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def extract_mailto_from_html(html: str) -> Optional[str]:
    soup = BeautifulSoup(html, "lxml")
    a = soup.find("a", href=lambda h: bool(h and h.lower().startswith("mailto:")))
    if not a:
        return None
    href = a.get("href", "")
    email = href.split(":", 1)[1].split("?", 1)[0].strip()
    # basic validation
    if re.match(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@([A-Za-z0-9-]+\.)+[A-Za-z]{2,}$", email):
        return email
    return None


def save_list(path: str, items: Iterable[str]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        for it in items:
            f.write(it.rstrip() + "\n")


def append_contacts_to_csv(path: str, rows: Iterable[Tuple[str, str, str, str]]) -> int:
    # rows: (name,email,affiliation,source_url)
    written = 0
    # Check existing emails to avoid duplicates
    existing = set()
    try:
        with open(path, "r", encoding="utf-8", newline="") as rf:
            reader = csv.DictReader(rf)
            for r in reader:
                em = (r.get("email") or "").strip().lower()
                if em:
                    existing.add(em)
    except FileNotFoundError:
        pass

    with open(path, "a", encoding="utf-8", newline="") as wf:
        writer = csv.writer(wf)
        for name, email, affiliation, src in rows:
            key = (email or "").strip().lower()
            if not key or key in existing:
                continue
            writer.writerow([name or "", email, affiliation or "", src or ""])
            existing.add(key)
            written += 1
    return written


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--directory-url", default=DIRECTORY_URL_DEFAULT)
    p.add_argument("--out-names", default="data/michigan_names.txt")
    p.add_argument("--out-slugs", default="data/michigan_slugs.txt")
    p.add_argument("--out-contacts-csv", default="data/michigan_contacts.csv")
    p.add_argument("--append-to", default="data/law_contacts.csv")
    p.add_argument("--affiliation", default="University of Michigan")
    p.add_argument("--delay", type=float, default=0.8)
    args = p.parse_args()

    print(f"Fetching directory: {args.directory_url}")
    html = fetch_html(args.directory_url, delay=args.delay)
    names = parse_directory_names(html)
    print(f"Found {len(names)} names")

    save_list(args.out_names, names)

    slugs = [slugify(n) for n in names]
    save_list(args.out_slugs, slugs)

    # Build profile URLs and fetch each to extract email
    rows = []
    for name, slug in zip(names, slugs):
        profile_url = args.directory_url.rstrip("/") + "/" + slug
        try:
            profile_html = fetch_html(profile_url, delay=args.delay)
        except Exception as e:
            print(f"Failed to fetch {profile_url}: {e}")
            continue
        email = extract_mailto_from_html(profile_html)
        if email:
            rows.append((name, email, args.affiliation, profile_url))
            print(f"Found: {name} -> {email}")
        else:
            print(f"No email found for {name} at {profile_url}")

    # Save per-site contacts CSV
    if rows:
        with open(args.out_contacts_csv, "w", encoding="utf-8", newline="") as cf:
            writer = csv.writer(cf)
            writer.writerow(["name", "email", "affiliation", "source_url"])
            for r in rows:
                writer.writerow(r)
        appended = append_contacts_to_csv(args.append_to, rows)
        print(f"Appended {appended} rows to {args.append_to}")
    else:
        print("No contacts to append.")


if __name__ == "__main__":
    main()


