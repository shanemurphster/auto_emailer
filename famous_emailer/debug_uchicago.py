from __future__ import annotations

import argparse
import json
import sys

from lawquotecollector.scraper import scrape_directory


def main(argv: list[str] | None = None) -> int:
	parser = argparse.ArgumentParser(description="Debug UChicago scraper: print scraped contacts")
	parser.add_argument("url", help="Directory URL to scrape")
	parser.add_argument("--site", default="uchicago", help="Site key to use")
	parser.add_argument("--affiliation", default="University of Chicago Law School")
	parser.add_argument("--skip-robots", action="store_true", help="Skip robots.txt checks")
	parser.add_argument("--use-playwright", action="store_true", help="Use Playwright for JS rendering")
	args = parser.parse_args(argv or sys.argv[1:])

	try:
		contacts = scrape_directory(
			url=args.url,
			affiliation=args.affiliation,
			source_url=args.url,
			site=args.site,
			skip_robots=args.skip_robots,
			use_playwright=args.use_playwright,
		)
	except Exception as e:
		print("Error scraping page:", e, file=sys.stderr)
		return 2

	print(f"Scraped {len(contacts)} contacts")
	for i, c in enumerate(contacts, start=1):
		# print a compact JSON-like view
		print(f"{i}: name={c.name!r}, email={c.email!r}, affiliation={c.affiliation!r}, source_url={c.source_url!r}")

	return 0


if __name__ == "__main__":
	sys.exit(main())



