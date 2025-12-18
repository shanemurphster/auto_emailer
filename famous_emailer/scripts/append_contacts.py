#!/usr/bin/env python3
"""
Append contacts from a source CSV into data/law_contacts.csv, skipping duplicate emails.

The source CSV may have columns:
  - name,profile_url,email,source_url
  - name,email,profile_url,source_url
  - any CSV with an 'email' column

Usage:
  python scripts/append_contacts.py --source data/columbia_names.csv --affiliation "Columbia Law School"
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from typing import Set


def read_existing_emails(path: str) -> Set[str]:
    emails = set()
    if not os.path.exists(path):
        return emails
    with open(path, newline="", encoding="utf-8") as fh:
        try:
            reader = csv.DictReader(fh)
        except Exception:
            return emails
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
        try:
            reader = csv.DictReader(fh)
        except Exception:
            return names
        for r in reader:
            n = (r.get("name") or "").strip().lower()
            if n:
                names.add(n)
    return names


def iter_source_rows(path: str):
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for r in reader:
            # normalize keys
            name = (r.get("name") or r.get("Name") or "").strip()
            email = (r.get("email") or r.get("Email") or "").strip()
            profile_url = (r.get("profile_url") or r.get("profile") or r.get("profileUrl") or "").strip()
            source_url = (r.get("source_url") or r.get("source") or r.get("source_url") or profile_url).strip()
            yield {"name": name, "email": email, "profile_url": profile_url, "source_url": source_url}


def append_rows(law_contacts_path: str, rows, affiliation: str) -> int:
    header = ["name", "email", "affiliation", "source_url"]
    exists = os.path.exists(law_contacts_path)
    written = 0
    with open(law_contacts_path, "a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=header)
        if not exists:
            writer.writeheader()
        for r in rows:
            writer.writerow(
                {
                    "name": r.get("name") or "",
                    "email": r.get("email") or "",
                    "affiliation": affiliation or "",
                    "source_url": r.get("source_url") or "",
                }
            )
            written += 1
    return written


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--source", required=True, help="Source CSV with email column (e.g. data/columbia_names.csv)")
    p.add_argument("--affiliation", default="", help="Affiliation string to add to law_contacts rows")
    p.add_argument("--law-contacts", default="data/law_contacts.csv", help="Path to global contacts CSV")
    p.add_argument("--dedupe-by-name", action="store_true", help="Also skip rows whose name already exists in law-contacts (case-insensitive)")
    args = p.parse_args(argv)

    if not os.path.exists(args.source):
        print(f"Source file not found: {args.source}", file=sys.stderr)
        return 2

    existing = read_existing_emails(args.law_contacts)
    existing_names = set()
    if args.dedupe_by_name:
        existing_names = read_existing_names(args.law_contacts)

    to_append = []
    for r in iter_source_rows(args.source):
        email = (r.get("email") or "").strip().lower()
        if not email:
            # skip rows without an email
            continue
        if "@" not in email:
            # skip obviously invalid emails
            continue
        if email in existing:
            continue
        name = (r.get("name") or "").strip().lower()
        if args.dedupe_by_name and name and name in existing_names:
            continue
        existing.add(email)
        to_append.append(r)

    if not to_append:
        print("No new contacts to append.")
        return 0

    written = append_rows(args.law_contacts, to_append, args.affiliation)
    print(f"Appended {written} rows to {args.law_contacts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


