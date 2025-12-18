from __future__ import annotations

import time
from typing import List, Optional, Set
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from bs4 import BeautifulSoup, Tag

from ..storage import Contact
from ..validators import is_valid_email
from ..scraper import _fetch_html


PAGE_DELAY_S = 1.2
END_PAGE = 20  # Adjust if needed; Penn State has fewer pages than Yale


def _set_page(url: str, page: int) -> str:
	parsed = urlparse(url)
	q = parse_qs(parsed.query)
	q["page"] = [str(page)]
	new_query = urlencode({k: v[0] for k, v in q.items()})
	return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))


def _extract_email(href: str) -> Optional[str]:
	if not href.lower().startswith("mailto:"):
		return None
	addr = href.split(":", 1)[1]
	addr = addr.split("?", 1)[0].strip()
	return addr or None


def _nearest_name_from_email_anchor(anchor: Tag) -> Optional[str]:
	anchor_text = (anchor.get_text(" ", strip=True) or "").strip()
	if anchor_text and "@" not in anchor_text and len(anchor_text.split()) <= 6:
		return anchor_text

	parent = anchor.parent
	if isinstance(parent, Tag):
		for sib in list(parent.children):
			if not isinstance(sib, Tag):
				continue
			text = sib.get_text(" ", strip=True)
			if not text:
				continue
			if sib.name in {"h1", "h2", "h3", "h4", "h5", "h6", "strong"}:
				if "@" not in text and len(text.split()) <= 8:
					return text
			cls = " ".join(sib.get("class", []))
			if any(token in cls.lower() for token in ["name", "person", "faculty", "profile"]):
				if "@" not in text and 1 <= len(text.split()) <= 8:
					return text

	ancestor = parent
	steps = 0
	while isinstance(ancestor, Tag) and steps < 3:
		for candidate in ancestor.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "strong"], limit=3):
			text = candidate.get_text(" ", strip=True)
			if text and "@" not in text and len(text.split()) <= 8:
				return text
		ancestor = ancestor.parent
		steps += 1
	return None


def _contacts_from_soup(soup: BeautifulSoup, page_url: str, affiliation: Optional[str]) -> List[Contact]:
	contacts: List[Contact] = []
	seen_local: Set[str] = set()

	for item in soup.select('.directory-item'):
		for a in item.select('a[href^="mailto:"]'):
			email = _extract_email(a.get("href", ""))
			if not email or not is_valid_email(email):
				continue
			key = email.strip().lower()
			if key in seen_local:
				continue
			seen_local.add(key)
			name = _nearest_name_from_email_anchor(a)
			contacts.append(Contact(name=name, email=email, affiliation=affiliation, source_url=page_url))
	return contacts


def parse_contacts(
	soup: BeautifulSoup,
	page_url: str,
	affiliation: Optional[str],
	source_url: Optional[str],
) -> List[Contact]:
	contacts = _contacts_from_soup(soup, page_url, affiliation)
	seen_emails: Set[str] = {c.email.strip().lower() for c in contacts}

	qs = parse_qs(urlparse(page_url).query)
	start_page = int(qs.get("page", ["0"])[0])
	current_page = start_page + 1

	while current_page <= END_PAGE:
		next_url = _set_page(page_url, current_page)
		time.sleep(PAGE_DELAY_S)
		try:
			next_html = _fetch_html(next_url)
		except Exception:
			break
		next_soup = BeautifulSoup(next_html, "lxml")
		new_contacts = _contacts_from_soup(next_soup, next_url, affiliation)
		for c in new_contacts:
			key = c.email.strip().lower()
			if key in seen_emails:
				continue
			seen_emails.add(key)
			contacts.append(c)
		current_page += 1

	return contacts




