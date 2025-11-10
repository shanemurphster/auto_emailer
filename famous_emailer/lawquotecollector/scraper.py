from __future__ import annotations

import time
from typing import List, Optional
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from urllib.robotparser import RobotFileParser

from .validators import is_valid_email
from .storage import Contact
from .sites import get as get_parser


DEFAULT_USER_AGENT = (
	"LawQuoteCollectorBot/1.0 (+research contact; github: local project)"
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


def _fetch_html(url: str, timeout_s: int = 20) -> str:
	headers = {"User-Agent": DEFAULT_USER_AGENT}
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
) -> List[Contact]:
	"""
	Scrape a single faculty directory page for visible `mailto:` links and
	attempt to find associated names nearby.

	- Respects robots.txt for the specific URL
	- Single-page only (no pagination walking)
	- Returns unique contacts by email
	"""
	if not _robots_allows(url):
		raise PermissionError(
			f"robots.txt disallows fetching this page: {url}. Aborting out of respect for site policies."
		)

	# Light politeness delay before the single request
	time.sleep(max(0.0, polite_delay_s))
	html = _fetch_html(url)
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


