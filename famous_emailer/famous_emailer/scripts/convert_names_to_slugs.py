#!/usr/bin/env python3
"""
Generate slug mapping and slugs list from a names CSV that contains profile URLs.

Input (default): data/harvard_names.csv with columns: name,profile_url,source_url
Outputs:
  - data/harvard_name_slug_map.csv  (name,slug,profile_url,source_url)
  - data/harvard_slugs.txt         (one slug per line)

Usage:
    python scripts/convert_names_to_slugs.py --input data/harvard_names.csv
"""
from __future__ import annotations

import argparse
import csv
from urllib.parse import urlparse
from typing import List, Tuple


def extract_slug_from_url(url: str) -> str:
    if not url:
        return ""
    path = urlparse(url).path
    if path.endswith("/"):
        path = path[:-1]
    parts = [p for p in path.split("/") if p]
    return parts[-1] if parts else ""


def read_names(path: str) -> List[Tuple[str, str, str]]:
    rows = []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for r in reader:
            name = r.get("name", "").strip()
            profile_url = r.get("profile_url", "").strip()
            source_url = r.get("source_url", "").strip()
            rows.append((name, profile_url, source_url))
    return rows


def write_mapping_and_slugs(mapping_path: str, slugs_path: str, rows: List[Tuple[str, str, str]]) -> None:
    with open(mapping_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["name", "slug", "profile_url", "source_url"])
        slugs = []
        for name, profile_url, source_url in rows:
            slug = extract_slug_from_url(profile_url)
            slugs.append(slug)
            writer.writerow([name, slug, profile_url, source_url])

    # write unique slugs
    unique_slugs = []
    seen = set()
    for s in slugs:
        if s and s not in seen:
            seen.add(s)
            unique_slugs.append(s)

    with open(slugs_path, "w", encoding="utf-8") as fh:
        for s in unique_slugs:
            fh.write(s + "\n")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", default="data/harvard_names.csv")
    p.add_argument("--mapping", default="data/harvard_name_slug_map.csv")
    p.add_argument("--slugs", default="data/harvard_slugs.txt")
    args = p.parse_args()

    rows = read_names(args.input)
    if not rows:
        print(f"No rows read from {args.input}")
        return 2

    write_mapping_and_slugs(args.mapping, args.slugs, rows)
    print(f"Wrote mapping to {args.mapping} and slugs to {args.slugs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import os
import re
from typing import List, Tuple


def slugify(name: str) -> str:
    """Lowercase name, replace non-alnum with dashes, collapse dashes."""
    s = name.strip().lower()
    # Replace unicode apostrophes and weird spaces
    s = s.replace("’", "").replace("‘", "").replace("·", "")
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-{2,}", "-", s)
    return s.strip("-")


def read_names(path: str) -> List[str]:
    """Read a newline-separated names file. Support UTF-8 BOM."""
    # Try utf-8-sig to drop BOM if present, fallback to utf-8
    encodings = ("utf-8-sig", "utf-8")
    for enc in encodings:
        try:
            with open(path, "r", encoding=enc) as f:
                lines = [l.strip() for l in f.readlines()]
            return [l for l in lines if l]
        except FileNotFoundError:
            raise
        except Exception:
            continue
    # Final fallback: read binary and decode ignoring errors
    with open(path, "rb") as f:
        raw = f.read()
    text = raw.decode("utf-8", errors="ignore")
    return [l.strip() for l in text.splitlines() if l.strip()]


def save_list(path: str, items: List[str]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        for it in items:
            f.write(it + "\n")


def save_mapping_csv(path: str, rows: List[Tuple[str, str]]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "slug"])
        for name, slug in rows:
            writer.writerow([name, slug])


def main() -> None:
    p = argparse.ArgumentParser(description="Convert names to lowercase-dashed slugs for Michigan profile URLs.")
    p.add_argument("--names-file", default="michigan_names.txt", help="Input newline-separated names file")
    p.add_argument("--out-slugs", default="data/michigan_slugs.txt", help="Output slugs file (one per line)")
    p.add_argument("--out-mapping-csv", default="data/michigan_name_slug_map.csv", help="CSV mapping name->slug")
    p.add_argument("--preview", type=int, default=30, help="Number of mappings to preview")
    args = p.parse_args()

    names = read_names(args.names_file)
    rows = [(n, slugify(n)) for n in names]
    slugs = [s for _, s in rows]

    save_list(args.out_slugs, slugs)
    save_mapping_csv(args.out_mapping_csv, rows)
    print(f"Wrote {len(slugs)} slugs to {args.out_slugs} and mapping to {args.out_mapping_csv}")
    print("\nPreview (first {0}):".format(min(args.preview, len(rows))))
    for name, slug in rows[: args.preview]:
        print(f"{name} -> {slug}")


if __name__ == "__main__":
    main()


