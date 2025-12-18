#!/usr/bin/env python3
from __future__ import annotations

"""
Fetch emails from individual University of Michigan Law faculty profile pages.

Usage:
  - Prepare a newline-separated names file (one name per line), e.g.:
      data/michigan_names.txt
  - Names will be slugified to lowercase dash-separated tokens:
      "Richard D. Friedman" -> "richard-d-friedman"
  - Profile URLs are constructed by joining the base URL and the slug.
  - The script fetches each profile, extracts the first mailto: href, and
    appends name,email,affiliation,source_url rows to `data/law_contacts.csv`.

Notes:
  - Uses a browser-like User-Agent and retry/backoff to avoid trivial 403s.
  - Keeps a small delay between requests to be polite.
"""

import argparse
import csv
import re
import time
from typing import Iterable, List, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup


def slugify(name: str) -> str:
    s = name.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-{2,}", "-", s)
    return s.strip("-")


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.google.com/",
        }
    )
    retry_strategy = Retry(
        total=3,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"],
        backoff_factor=0.5,
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def extract_mailto(html: str) -> Optional[str]:
    soup = BeautifulSoup(html, "lxml")
    a = soup.find("a", href=lambda h: bool(h and h.lower().startswith("mailto:")))
    if not a:
        return None
    href = a.get("href", "")
    email = href.split(":", 1)[1].split("?", 1)[0].strip()
    # simple validation
    if re.match(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@([A-Za-z0-9-]+\.)+[A-Za-z]{2,}$", email):
        return email
    return None


def read_names(path: str) -> List[str]:
    with open(path, "r", encoding="utf-8") as f:
        lines = [l.strip() for l in f.readlines()]
    return [l for l in lines if l]


def append_contacts_to_csv(path: str, rows: Iterable[Tuple[str, str, str, str]]) -> int:
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
    p = argparse.ArgumentParser(description="Fetch emails from Michigan profile pages given a names file.")
    p.add_argument("--names-file", required=True, help="Newline-separated names file (one name per line)")
    p.add_argument("--base-url", default="https://michigan.law.umich.edu/faculty-and-scholarship/our-faculty/", help="Base profile URL (trailing slash recommended)")
    p.add_argument("--affiliation", default="University of Michigan", help="Affiliation to write into CSV")
    p.add_argument("--append-to", default="data/law_contacts.csv", help="CSV to append contacts to")
    p.add_argument("--out-site-csv", default="data/michigan_contacts.csv", help="Per-site CSV to write results to")
    p.add_argument("--delay", type=float, default=0.8, help="Delay between requests (seconds)")
    args = p.parse_args()

    names = read_names(args.names_file)
    print(f"Read {len(names)} names from {args.names_file}")
    session = make_session()

    rows = []
    for name in names:
        slug = slugify(name)
        profile_url = args.base_url.rstrip("/") + "/" + slug
        try:
            time.sleep(args.delay)
            resp = session.get(profile_url, timeout=15)
            resp.raise_for_status()
            email = extract_mailto(resp.text)
            if email:
                rows.append((name, email, args.affiliation, profile_url))
                print(f"Found: {name} -> {email}")
            else:
                print(f"No email found for: {name} ({profile_url})")
        except Exception as e:
            print(f"Error fetching {profile_url}: {e}")

    # save per-site CSV
    if rows:
        with open(args.out_site_csv, "w", encoding="utf-8", newline="") as cf:
            w = csv.writer(cf)
            w.writerow(["name", "email", "affiliation", "source_url"])
            for r in rows:
                w.writerow(r)
        appended = append_contacts_to_csv(args.append_to, rows)
        print(f"Appended {appended} new contacts to {args.append_to}")
    else:
        print("No contacts found.")


if __name__ == "__main__":
    main()


