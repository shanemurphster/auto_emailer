from __future__ import annotations

import re
import time
import unicodedata
from typing import List, Optional

from bs4 import BeautifulSoup

from ..storage import Contact
from ..validators import is_valid_email
from ..scraper import _fetch_html, _robots_allows


PROFILE_DELAY_S = 1.0


def _slugify_name(name: str) -> str:
	# Normalize unicode, strip accents
	norm = unicodedata.normalize("NFKD", name)
	# Keep only letters, numbers, and spaces; drop punctuation
	clean = re.sub(r"[^A-Za-z0-9\s]", "", norm)
	# Collapse whitespace to single hyphens
	slug = re.sub(r"\s+", "-", clean.strip())
	return slug.lower()


def _extract_profile_email(profile_html: str) -> Optional[str]:
	soup = BeautifulSoup(profile_html, "lxml")
	# Primary: Harvard profile markup
	primary = soup.select_one('p.contact_email a[href^="mailto:"]')
	if primary:
		h = primary.get("href", "")
		addr = h.split(":", 1)[1].split("?", 1)[0].strip() if ":" in h else ""
		if addr and is_valid_email(addr):
			return addr
	# Fallback: any mailto on the page
	for a in soup.select('a[href^="mailto:"]'):
		href = a.get("href", "")
		addr = href.split(":", 1)[1].split("?", 1)[0].strip() if ":" in href else ""
		if addr and is_valid_email(addr):
			return addr
	return None


def parse_contacts(
	soup: BeautifulSoup,
	page_url: str,
	affiliation: Optional[str],
	source_url: Optional[str],
) -> List[Contact]:
	contacts: List[Contact] = []
	for el in soup.select('.faculty-feed__item-title'):
		name = (el.get_text(" ", strip=True) or "").strip()
		if not name:
			continue
		slug = _slugify_name(name)
		profile_url = page_url.rstrip("/") + "/" + slug + "/"
		# Respect robots for profile page
		if not _robots_allows(profile_url):
			continue
		time.sleep(PROFILE_DELAY_S)
		try:
		html = _fetch_html(profile_url)
		except Exception:
			continue
		email = _extract_profile_email(html)
		if not email:
			continue
		contacts.append(
			Contact(
				name=name,
				email=email,
				affiliation=affiliation,
				source_url=profile_url,
			)
		)
	return contacts


