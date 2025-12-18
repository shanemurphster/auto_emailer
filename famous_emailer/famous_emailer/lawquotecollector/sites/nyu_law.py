from __future__ import annotations

from typing import List, Optional, Set
from bs4 import BeautifulSoup, Tag

from ..storage import Contact
from ..validators import is_valid_email


def _extract_email(href: str) -> Optional[str]:
	if not href:
		return None
	h = href.strip()
	if not h.lower().startswith("mailto:"):
		return None
	addr = h.split(":", 1)[1]
	addr = addr.split("?", 1)[0].strip()
	return addr or None


def parse_contacts(
	soup: BeautifulSoup,
	page_url: str,
	affiliation: Optional[str],
	source_url: Optional[str],
) -> List[Contact]:
	"""
	Parser for NYU faculty listings where rows contain multiple elements with
	class="list". The faculty name appears in an element with classes
	`list facultyName`. The email (mailto:) is typically inside the fourth
	element with class="list" within the same row/container.
	"""
	contacts: List[Contact] = []
	seen_emails: Set[str] = set()

	# Find all name cells
	for name_cell in soup.select(".list.facultyName"):
		name_text = (name_cell.get_text(" ", strip=True) or "").strip() or None
		email: Optional[str] = None

		# Prefer the sibling 4th .list element if present
		parent = name_cell.parent
		if isinstance(parent, Tag):
			list_cells = parent.find_all(class_="list")
			if len(list_cells) >= 4:
				candidate = list_cells[3]
				a = candidate.find("a", href=lambda h: bool(h and h.lower().startswith("mailto:")))
				if a:
					email = _extract_email(a.get("href", ""))
			# fallback: any mailto link under the same parent
			if not email:
				a = parent.find("a", href=lambda h: bool(h and h.lower().startswith("mailto:")))
				if a:
					email = _extract_email(a.get("href", ""))

		# Validate and append
		if email and is_valid_email(email):
			key = email.strip().lower()
			if key in seen_emails:
				continue
			seen_emails.add(key)
			contacts.append(Contact(name=name_text, email=email, affiliation=affiliation, source_url=page_url))

	return contacts


