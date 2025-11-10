from __future__ import annotations

import argparse
import sys
from typing import List

from .scraper import scrape_directory
from .validators import is_valid_email
from .storage import Contact, save_contacts_csv, save_contacts_sqlite, dedupe_contacts
from .importers import parse_email_lines


def _parse_args(argv: list[str]) -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description="LawQuoteCollector: ethically scrape public faculty contacts and store locally"
	)
	sub = parser.add_subparsers(dest="command", required=True)

	scrape = sub.add_parser("scrape", help="Scrape a single faculty directory page")
	scrape.add_argument("url", help="Faculty directory URL to parse (single page)")
	scrape.add_argument("--affiliation", help="Affiliation to attach to all results", default=None)
	scrape.add_argument("--source-url", help="Source URL to store (defaults to the scraped URL)", default=None)
	scrape.add_argument("--out", help="Output path (csv or sqlite)", default="data/law_contacts.csv")
	scrape.add_argument("--format", choices=["csv", "sqlite"], default="csv")
	scrape.add_argument("--append", action="store_true", help="Append to CSV if it exists")
	scrape.add_argument("--site", help="Optional site key to use a site-specific parser", default=None)

	manual = sub.add_parser(
		"import-list",
		help="Convert a list of emails (newline or CSV format) into contacts and store them",
	)
	manual.add_argument("--input", help="Input file path or - for stdin", default="-")
	manual.add_argument("--affiliation", help="Affiliation to attach to all contacts", default=None)
	manual.add_argument(
		"--source-url",
		help="Source URL or description for manual entries",
		default="manual_list",
	)
	manual.add_argument("--out", help="Output path (csv or sqlite)", default="data/law_contacts.csv")
	manual.add_argument("--format", choices=["csv", "sqlite"], default="csv")
	manual.add_argument("--append", action="store_true", help="Append to CSV if it exists")

	return parser.parse_args(argv)


def _save(contacts: List[Contact], out_path: str, fmt: str, append: bool) -> int:
	contacts = [c for c in contacts if is_valid_email(c.email)]
	contacts = dedupe_contacts(contacts)
	if fmt == "csv":
		return save_contacts_csv(out_path, contacts, append=append)
	if fmt == "sqlite":
		return save_contacts_sqlite(out_path, contacts)
	raise ValueError(f"Unsupported format: {fmt}")


def main(argv: list[str] | None = None) -> int:
	args = _parse_args(argv or sys.argv[1:])
	if args.command == "scrape":
		contacts = scrape_directory(
			url=args.url,
			affiliation=args.affiliation,
			source_url=args.source_url,
			site=args.site,
		)
		count = _save(contacts, args.out, args.format, args.append)
		print(f"Saved {count} contacts to {args.out}")
		return 0
	if args.command == "import-list":
		if args.input == "-":
			lines = sys.stdin.read().splitlines()
		else:
			with open(args.input, encoding="utf-8") as f:
				lines = f.readlines()
		contacts = parse_email_lines(
			lines,
			affiliation=args.affiliation,
			source_url=args.source_url,
		)
		count = _save(contacts, args.out, args.format, args.append)
		print(f"Saved {count} contacts to {args.out}")
		return 0
	return 1


if __name__ == "__main__":
	sys.exit(main())


