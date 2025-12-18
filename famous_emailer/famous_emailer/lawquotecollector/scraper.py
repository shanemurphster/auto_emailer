from __future__ import annotations

import time
from typing import List, Optional
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from urllib.robotparser import RobotFileParser

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

from .validators import is_valid_email
from .storage import Contact
from .sites import get as get_parser


DEFAULT_USER_AGENT = (
	"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
)


def _robots_allows(url: str, user_agent: str = DEFAULT_USER_AGENT) -> bool:
	parsed = urlparse(url)
	robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
	rp = RobotFileParser()
	try:
		rp.set_url(robots_url)
		rp.read()
	except Exception:
		# If robots.txt is unavailable, be conservative: allow only the exact page fetch
		return True
	return rp.can_fetch(user_agent, url)


def _fetch_html(url: str, timeout_s: int = 20, use_playwright: bool = False) -> str:
	if use_playwright and PLAYWRIGHT_AVAILABLE:
		with sync_playwright() as p:
			browser = p.chromium.launch(headless=True)
			context = browser.new_context(
				user_agent=DEFAULT_USER_AGENT,
				viewport={"width": 1280, "height": 720},
			)
			page = context.new_page()
			page.goto(url, timeout=timeout_s * 1000)
			page.wait_for_load_state("networkidle")
			html = page.content()
			browser.close()
			return html
	else:
		# Use custom headers for Harvard to match the working script
		if "hls.harvard.edu" in url:
			headers = {"User-Agent": "LawQuoteCollector (+mailto:your@upenn.edu)"}
		else:
			headers = {
				"User-Agent": DEFAULT_USER_AGENT,
				"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
				"Accept-Language": "en-US,en;q=0.5",
				"Accept-Encoding": "gzip, deflate, br",
				"DNT": "1",
				"Connection": "keep-alive",
				"Upgrade-Insecure-Requests": "1",
			}
		resp = requests.get(url, headers=headers, timeout=timeout_s)
		resp.raise_for_status()
		return resp.text


def _infer_affiliation_from_url(url: str) -> str:
	parsed = urlparse(url)
	host = parsed.netloc
	return host


def scrape_directory(
	url: str,
	affiliation: Optional[str] = None,
	source_url: Optional[str] = None,
	polite_delay_s: float = 1.5,
	site: Optional[str] = None,
	skip_robots: bool = False,
	use_playwright: bool = False,
) -> List[Contact]:
	"""
	Scrape a single faculty directory page for visible `mailto:` links and
	attempt to find associated names nearby.

	- Respects robots.txt for the specific URL (unless skip_robots=True)
	- Single-page only (no pagination walking)
	- Returns unique contacts by email
	"""
	if not skip_robots and not _robots_allows(url):
		raise PermissionError(
			f"robots.txt disallows fetching this page: {url}. Aborting out of respect for site policies."
		)

	# Light politeness delay before the single request
	time.sleep(max(0.0, polite_delay_s))
	html = _fetch_html(url, use_playwright=use_playwright)
	soup = BeautifulSoup(html, "lxml")

	parser = get_parser(site)
	base_affiliation = affiliation or _infer_affiliation_from_url(url)
	contacts = parser(soup, url, base_affiliation, source_url or url)

	# Deduping by email happens in storage layer, but also local pass here
	seen = set()
	unique: List[Contact] = []
	for c in contacts:
		key = c.email.strip().lower()
		if key in seen:
			continue
		seen.add(key)
		unique.append(c)
	return unique


