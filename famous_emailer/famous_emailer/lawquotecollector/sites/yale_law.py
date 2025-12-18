from __future__ import annotations

import time
from typing import List, Optional, Set, Tuple
import re
from urllib.parse import urlencode, urlparse, parse_qs, urlunparse

from bs4 import BeautifulSoup, Tag

from ..storage import Contact
from ..validators import is_valid_email
from ..scraper import _fetch_html, _robots_allows


PAGE_DELAY_S = 1.2
END_PAGE = 28  # inclusive


def _set_page(url: str, page: int) -> str:
	parsed = urlparse(url)
	q = parse_qs(parsed.query)
	q["page"] = [str(page)]
	new_query = urlencode({k: v[0] for k, v in q.items()})
	return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))


def _extract_email_from_mailto(href: str) -> Optional[str]:
	if not href.lower().startswith("mailto:"):
		return None
	addr = href.split(":", 1)[1]
	addr = addr.split("?", 1)[0].strip()
	return addr or None


def _nearest_name_from_email_anchor(anchor: Tag) -> Optional[str]:
    # Prefer a heading within the same container
    container = anchor
    hops = 0
    while isinstance(container, Tag) and hops < 4:
        # Look for common heading tags within this container
        for h in container.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "strong"], limit=2):
            text = (h.get_text(" ", strip=True) or "").strip()
            if text and "@" not in text and 1 <= len(text.split()) <= 12:
                return text
        container = container.parent
        hops += 1

    # Search previous headings in the document order
    for prev in anchor.find_all_previous(["h1", "h2", "h3", "h4", "h5", "h6", "strong"], limit=10):
        text = (prev.get_text(" ", strip=True) or "").strip()
        if text and "@" not in text and 1 <= len(text.split()) <= 12:
            return text

    # Fallback to the anchor text itself if it looks like a name (rare)
    txt = (anchor.get_text(" ", strip=True) or "").strip()
    if txt and "@" not in txt and 1 <= len(txt.split()) <= 12:
        return txt
    return None


def _nearest_name_for_element(element: Tag) -> Optional[str]:
    container = element
    hops = 0
    while isinstance(container, Tag) and hops < 4:
        for h in container.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "strong"], limit=3):
            text = (h.get_text(" ", strip=True) or "").strip()
            if text and "@" not in text and 1 <= len(text.split()) <= 12:
                return text
        container = container.parent
        hops += 1
    for prev in element.find_all_previous(["h1", "h2", "h3", "h4", "h5", "h6", "strong"], limit=10):
        text = (prev.get_text(" ", strip=True) or "").strip()
        if text and "@" not in text and 1 <= len(text.split()) <= 12:
            return text
    return None


EMAIL_TEXT_REGEX = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def _contacts_from_soup(soup: BeautifulSoup, page_url: str, affiliation: Optional[str]) -> List[Contact]:
    contacts: List[Contact] = []
    seen_local: Set[str] = set()

    # 1) Anchor-based emails anywhere on the page (broad catch)
    for a in soup.select('a[href^="mailto:"]'):
        email = _extract_email_from_mailto(a.get("href", ""))
        if not email or not is_valid_email(email):
            continue
        key = email.strip().lower()
        if key in seen_local:
            continue
        seen_local.add(key)
        name = _nearest_name_from_email_anchor(a)
        contacts.append(Contact(name=name, email=email, affiliation=affiliation, source_url=page_url))

    # 2) Plain-text emails inside field__item blocks
    for block in soup.select('.field__item'):
        text = block.get_text(" ", strip=True) or ""
        for match in EMAIL_TEXT_REGEX.findall(text):
            email = match.strip()
            if not is_valid_email(email):
                continue
            key = email.lower()
            if key in seen_local:
                continue
            seen_local.add(key)
            name = _nearest_name_for_element(block)
            contacts.append(Contact(name=name, email=email, affiliation=affiliation, source_url=page_url))

    return contacts


def parse_contacts(
	soup: BeautifulSoup,
	page_url: str,
	affiliation: Optional[str],
	source_url: Optional[str],
) -> List[Contact]:
	# Start with the provided soup/page
	contacts = _contacts_from_soup(soup, page_url, affiliation)
	seen_emails: Set[str] = {c.email.strip().lower() for c in contacts}

	# Determine starting page number from URL (default 0)
	qs = parse_qs(urlparse(page_url).query)
	start_page = int(qs.get("page", ["0"])[0])
	current_page = start_page + 1

    # Iterate forward through fixed end page (inclusive)
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


