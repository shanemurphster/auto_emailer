from __future__ import annotations

import argparse
import logging
import sys
from typing import List
import re

from .scraper import scrape_directory, _fetch_html, _robots_allows
from .validators import is_valid_email
from .storage import Contact, save_contacts_csv, save_contacts_sqlite, dedupe_contacts, update_names_in_csv
from .importers import parse_email_lines
from .sites import get as get_parser


def _parse_args(argv: list[str]) -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description="LawQuoteCollector: ethically scrape public faculty contacts and store locally"
	)
	sub = parser.add_subparsers(dest="command", required=True)

	# scrape
	scrape = sub.add_parser("scrape", help="Scrape a single faculty directory page")
	scrape.add_argument("url", help="Faculty directory URL to parse (single page)")
	scrape.add_argument("--affiliation", help="Affiliation to attach to all results", default=None)
	scrape.add_argument("--source-url", help="Source URL to store (defaults to the scraped URL)", default=None)
	scrape.add_argument("--out", help="Output path (csv or sqlite)", default="data/law_contacts.csv")
	scrape.add_argument("--format", choices=["csv", "sqlite"], default="csv")
	scrape.add_argument("--append", action="store_true", help="Append to CSV if it exists")
	scrape.add_argument("--site", help="Optional site key to use a site-specific parser", default=None)
	scrape.add_argument("--skip-robots", action="store_true", help="Skip robots.txt checks (use at your own risk)")
	scrape.add_argument("--use-playwright", action="store_true", help="Use Playwright for JS rendering (slower)")

	# reconcile: update names in an existing CSV by scraping a given page
	recon = sub.add_parser("reconcile", help="Reconcile names in an existing CSV using a site parser and URL")
	recon.add_argument("url", help="Faculty directory URL to parse (single page)")
	recon.add_argument("--site", help="Site key to use a site-specific parser", required=True)
	recon.add_argument("--infile", help="CSV file to update", default="data/law_contacts.csv")
	recon.add_argument("--affiliation", help="Affiliation to attach to scraped results", default=None)
	recon.add_argument("--skip-robots", action="store_true", help="Skip robots.txt checks (use at your own risk)")
	recon.add_argument("--use-playwright", action="store_true", help="Use Playwright for JS rendering (slower)")
	# (removed) fill-names-by-order: fill empty name fields using scraped names in order

	# scrape-names: scrape names from a page and write name-only rows to CSV
	names_cmd = sub.add_parser("scrape-names", help="Scrape names from a page and write name-only rows to CSV")
	names_cmd.add_argument("url", help="Faculty directory URL to parse (single page)")
	names_cmd.add_argument("--site", help="Site key to use a site-specific parser", required=True)
	names_cmd.add_argument("--affiliation", help="Affiliation to attach to scraped names", default=None)
	names_cmd.add_argument("--out", help="Output CSV path", default="data/law_contacts.csv")
	names_cmd.add_argument("--overwrite", action="store_true", help="Overwrite output CSV instead of appending")
	names_cmd.add_argument("--skip-robots", action="store_true", help="Skip robots.txt checks (use at your own risk)")
	names_cmd.add_argument("--use-playwright", action="store_true", help="Use Playwright for JS rendering (slower)")

	# manual import
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
	# Configure logging
	logging.basicConfig(
		level=logging.INFO,
		format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
		datefmt='%H:%M:%S'
	)

	args = _parse_args(argv or sys.argv[1:])
	if args.command == "scrape":
		print(f"Using site parser: {args.site}")
		contacts = scrape_directory(
			url=args.url,
			affiliation=args.affiliation,
			source_url=args.source_url,
			site=args.site,
			skip_robots=args.skip_robots,
			use_playwright=args.use_playwright,
		)
		count = _save(contacts, args.out, args.format, args.append)
		print(f"Saved {count} contacts to {args.out}")
		return 0

	if args.command == "reconcile":
		if not args.site or not args.url:
			print("reconcile requires --site and URL")
			return 2
		print(f"Using site parser: {args.site} to reconcile names from {args.url}")
		contacts = scrape_directory(
			url=args.url,
			affiliation=args.affiliation,
			source_url=args.url,
			site=args.site,
			skip_robots=args.skip_robots,
			use_playwright=args.use_playwright,
		)
		try:
			updated = update_names_in_csv(args.infile, contacts)
		except Exception as e:
			print(f"Error updating CSV: {e}")
			return 3
		print(f"Updated {updated} rows in {args.infile}")
		return 0
	# (removed) fill-names command handling

	if args.command == "scrape-names":
		if not args.site or not args.url:
			print("scrape-names requires --site and URL")
			return 2
		print(f"Using site parser: {args.site} to scrape names from {args.url}")
		# Respect robots.txt unless skipped
		if not args.skip_robots and not _robots_allows(args.url):
			print(f"robots.txt disallows fetching this page: {args.url}")
			return 2
		# Fetch HTML and call site parser directly to preserve profile-only names
		try:
			html = _fetch_html(args.url, use_playwright=args.use_playwright)
		except Exception as e:
			print(f"Error fetching page: {e}")
			return 3
		from bs4 import BeautifulSoup
		soup = BeautifulSoup(html, "lxml")
		parser = get_parser(args.site)
		contacts = parser(soup, args.url, args.affiliation, args.url)
		# Extract names (include profile-only names)
		names = [c.name for c in contacts if c.name]
		try:
			# Lazy import to avoid circulars if any
			from .storage import save_names_csv

			written = save_names_csv(args.out, names, affiliation=args.affiliation, source_url=args.url, overwrite=args.overwrite)
		except Exception as e:
			print(f"Error writing names CSV: {e}")
			return 3
		print(f"Wrote {written} name rows to {args.out}")
		return 0

	if args.command == "import-list":
		# Robust import: parse lines greedily for an email token and associate nearby name text.
		if args.input == "-":
			raw_lines = sys.stdin.read().splitlines()
		else:
			with open(args.input, encoding="utf-8") as f:
				raw_lines = f.read().splitlines()

		contacts = []
		# liberal email token regex (will be validated by is_valid_email)
		email_re = re.compile(r"([A-Za-z0-9.!#$%&'*+/=?^_`{|}~\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})")
		for raw in raw_lines:
			line = (raw or "").strip()
			if not line or line.startswith("#"):
				continue
			# try to find an email token anywhere
			m = email_re.search(line)
			if not m:
				# try comma-separated second token
				parts = [p.strip() for p in line.split(",")]
				if len(parts) >= 2 and is_valid_email(parts[1]):
					email = parts[1]
					name = parts[0] or None
				else:
					continue
			else:
				email = m.group(1).strip().rstrip(".,;:")
				# derive name by removing email token and common separators
				left = (line[: m.start()] or line[m.end():]).strip()
				# if left looks empty, try splitting on dash-like separators
				if not left:
					parts = re.split(r"\s*[-\u2012\u2013\u2014]\s*", line, maxsplit=1)
					if len(parts) == 2:
						left = parts[0].strip() or parts[1].strip()
				# clean common punctuation and trailing words like '–' or ':' or '('
				left = re.sub(r'^[\s\-\u2012\u2013\u2014\:\,]+', '', left).strip()
				left = re.sub(r'[\s\-\u2012\u2013\u2014\:\,]+$', '', left).strip()
				# remove trailing bracketed notes
				left = re.sub(r'[\(\[\{].*?[\)\]\}]$', '', left).strip()
				name = left or None

			# Validate email and append contact
			if not email or not is_valid_email(email):
				continue
			contacts.append(Contact(name=name, email=email, affiliation=args.affiliation, source_url=args.source_url))

		# Save parsed contacts
		count = _save(contacts, args.out, args.format, args.append)
		print(f"Saved {count} contacts to {args.out}")
		return 0
	return 1


if __name__ == "__main__":
	sys.exit(main())


