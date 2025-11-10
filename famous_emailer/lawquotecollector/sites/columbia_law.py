from __future__ import annotations

import time
from typing import List, Optional, Set
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse, unquote

from bs4 import BeautifulSoup, Tag

from ..storage import Contact
from ..validators import is_valid_email
from ..scraper import _fetch_html, _robots_allows


PAGE_DELAY_S = 1.0
MAX_PAGES = 40


def _with_page(url: str, page: int) -> str:
	parsed = urlparse(url)
	query = parse_qs(parsed.query)
	query["page"] = [str(page)]
	flat = urlencode({k: v[0] for k, v in query.items()})
	return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, flat, parsed.fragment))


def _extract_email(href: str) -> Optional[str]:
    if not href:
        return None
    lower = href.strip().lower()
    if not lower.startswith("mailto:"):
        return None
    addr = href.split(":", 1)[1]
    addr = addr.split("?", 1)[0].split("#", 1)[0].strip()
    addr = unquote(addr)
    return addr or None


def _candidate_text(node: Tag) -> Optional[str]:
	text = (node.get_text(" ", strip=True) or "").strip()
	if text and "@" not in text and 1 <= len(text.split()) <= 12:
		return text
	return None


def _find_name(anchor: Tag) -> Optional[str]:
	container = anchor
	for _ in range(5):
		if not isinstance(container, Tag):
			break
		# Check for known name classes within this container
		for selector in [".faculty__name", ".faculty-card__name", ".person__name"]:
			node = container.select_one(selector)
			if node:
				candidate = _candidate_text(node)
				if candidate:
					return candidate
		# Check heading tags inside this container
		for heading in container.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "strong"], limit=3):
			candidate = _candidate_text(heading)
			if candidate:
				return candidate
		container = container.parent

	# Fallback: look backwards in the DOM for recent headings
	for prev in anchor.find_all_previous(["h1", "h2", "h3", "h4", "h5", "h6", "strong"], limit=6):
		candidate = _candidate_text(prev)
		if candidate:
			return candidate

	# Last resort: anchor text itself
	return _candidate_text(anchor)



def _contacts_from_page(soup: BeautifulSoup, page_url: str, affiliation: Optional[str]) -> List[Contact]:
    contacts: List[Contact] = []
    # Columbia shows mailto links on listing pages; iterate all anchors and filter in Python
    for anchor in soup.find_all('a', href=True):
        email = _extract_email(anchor.get("href", ""))
		if not email or not is_valid_email(email):
			continue
		name = _find_name(anchor)
		contacts.append(
			Contact(
				name=name,
				email=email,
				affiliation=affiliation,
				source_url=page_url,
			)
		)
	return contacts


def parse_contacts(
	soup: BeautifulSoup,
	page_url: str,
	affiliation: Optional[str],
	source_url: Optional[str],
) -> List[Contact]:
	contacts = _contacts_from_page(soup, page_url, affiliation)
	seen: Set[str] = {c.email.strip().lower() for c in contacts}

	qs = parse_qs(urlparse(page_url).query)
	start_page = int(qs.get("page", ["0"])[0])
	current = start_page + 1

	while current - start_page <= MAX_PAGES:
		next_url = _with_page(page_url, current)
		time.sleep(PAGE_DELAY_S)
		try:
			html = _fetch_html(next_url)
		except Exception:
			break
		next_soup = BeautifulSoup(html, "lxml")
		page_contacts = _contacts_from_page(next_soup, next_url, affiliation)
		new_added = 0
		for c in page_contacts:
			key = c.email.strip().lower()
			if key in seen:
				continue
			seen.add(key)
			contacts.append(c)
			new_added += 1
		if new_added == 0:
			break
		current += 1

	return contacts


