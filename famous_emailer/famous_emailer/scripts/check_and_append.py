#!/usr/bin/env python3
"""
Check which rows from a source CSV are missing in the global contacts CSV and append only the missing ones.

This is a safer alternative to `append_contacts.py` that prints a summary before making changes.

Usage:
  python scripts/check_and_append.py --source data/columbia_contacts_playwright.csv --law-contacts data/law_contacts.csv --affiliation "Columbia Law School" --dedupe-by-name
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from typing import List, Dict, Set


def read_existing_emails(path: str) -> Set[str]:
    emails = set()
    if not os.path.exists(path):
        return emails
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for r in reader:
            e = (r.get("email") or "").strip().lower()
            if e:
                emails.add(e)
    return emails


def read_existing_names(path: str) -> Set[str]:
    names = set()
    if not os.path.exists(path):
        return names
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for r in reader:
            n = (r.get("name") or "").strip().lower()
            if n:
                names.add(n)
    return names


def read_source(path: str) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for r in reader:
            rows.append(r)
    return rows


def select_missing_rows(source_rows: List[Dict[str, str]], existing_emails: Set[str], existing_names: Set[str], dedupe_by_name: bool) -> List[Dict[str, str]]:
    missing: List[Dict[str, str]] = []
    seen_emails = set(existing_emails)
    seen_names = set(existing_names)
    for r in source_rows:
        email = (r.get("email") or "").strip().lower()
        if not email or "@" not in email:
            continue
        name = (r.get("name") or "").strip()
        lname = name.lower() if name else ""
        if email in seen_emails:
            continue
        if dedupe_by_name and lname and lname in seen_names:
            continue
        seen_emails.add(email)
        if lname:
            seen_names.add(lname)
        missing.append({"name": name, "email": r.get("email") or "", "affiliation": r.get("affiliation") or "", "profile_url": r.get("profile_url") or r.get("profile") or "", "source_url": r.get("source_url") or ""})
    return missing


def append_rows(path: str, rows: List[Dict[str, str]], affiliation: str) -> int:
    header = ["name", "email", "affiliation", "source_url"]
    exists = os.path.exists(path)
    written = 0
    with open(path, "a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=header)
        if not exists:
            writer.writeheader()
        for r in rows:
            writer.writerow({
                "name": r.get("name") or "",
                "email": r.get("email") or "",
                "affiliation": affiliation or r.get("affiliation") or "",
                "source_url": r.get("source_url") or r.get("profile_url") or ""
            })
            written += 1
    return written


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--source", required=True, help="Source CSV path (must include 'email' column)")
    p.add_argument("--law-contacts", default="data/law_contacts.csv", help="Global contacts CSV")
    p.add_argument("--affiliation", default="", help="Affiliation to write into appended rows (overrides source affiliation)")
    p.add_argument("--dedupe-by-name", action="store_true", help="Also skip rows whose name already exists in law_contacts (case-insensitive)")
    p.add_argument("--dry-run", action="store_true", help="Print summary only and do not modify files")
    args = p.parse_args(argv)

    if not os.path.exists(args.source):
        print(f"Source file not found: {args.source}", file=sys.stderr)
        return 2

    source_rows = read_source(args.source)
    if not source_rows:
        print("No rows found in source CSV", file=sys.stderr)
        return 2

    existing_emails = read_existing_emails(args.law_contacts)
    existing_names = set()
    if args.dedupe_by_name:
        existing_names = read_existing_names(args.law_contacts)

    missing = select_missing_rows(source_rows, existing_emails, existing_names, args.dedupe_by_name)

    print(f"Source rows: {len(source_rows)}")
    print(f"Existing emails in {args.law_contacts}: {len(existing_emails)}")
    print(f"Missing rows to append: {len(missing)}")
    if len(missing) > 0:
        print("Sample missing (first 10):")
        for r in missing[:10]:
            print(f"  {r['name']!r} <{r['email']}> {r.get('profile_url','')}")

    if args.dry_run:
        print("Dry run; no changes written.")
        return 0

    if not missing:
        print("Nothing to append.")
        return 0

    written = append_rows(args.law_contacts, missing, args.affiliation)
    print(f"Appended {written} rows to {args.law_contacts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


