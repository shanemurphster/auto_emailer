from __future__ import annotations

from typing import List, Optional
from bs4 import BeautifulSoup, Tag

from ..storage import Contact
from ..validators import is_valid_email


def _extract_email_from_mailto(href: str) -> Optional[str]:
	if not href.lower().startswith("mailto:"):
		return None
	address = href.split(":", 1)[1]
	address = address.split("?", 1)[0].strip()
	return address or None


def _nearest_name(anchor: Tag) -> Optional[str]:
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


def parse_contacts(
	soup: BeautifulSoup,
	page_url: str,
	affiliation: Optional[str],
	source_url: Optional[str],
) -> List[Contact]:
	contacts: List[Contact] = []
	base_affiliation = affiliation
	src = source_url or page_url
	for a in soup.find_all("a", href=True):
		email = _extract_email_from_mailto(a["href"]) or None
		if not email or not is_valid_email(email):
			continue
		name = _nearest_name(a)
		contacts.append(Contact(name=name, email=email, affiliation=base_affiliation, source_url=src))
	return contacts


