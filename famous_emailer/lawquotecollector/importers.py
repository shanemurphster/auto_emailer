from __future__ import annotations

import re
from typing import Iterable, List, Optional

from .storage import Contact
from .validators import is_valid_email


NAME_EMAIL_PATTERN = re.compile(r"^\s*(?P<name>[^<]+?)\s*<(?P<email>[^>]+)>\s*$")
NAME_DASH_EMAIL_PATTERN = re.compile(r"^\s*(?P<name>.+?)\s*[-–—]\s*(?P<email>[^\s]+)\s*$")


def _parse_csv_like(line: str) -> tuple[Optional[str], Optional[str]]:
	parts = [p.strip() for p in line.split(",")]
	if len(parts) < 2:
		return None, None
	first, second = parts[0], parts[1]
	if is_valid_email(first):
		return None if len(parts) < 2 else parts[1] or None, first
	if is_valid_email(second):
		return first or None, second
	return None, None


def parse_email_lines(
	lines: Iterable[str],
	affiliation: Optional[str] = None,
	source_url: Optional[str] = None,
) -> List[Contact]:
	contacts: List[Contact] = []
	for raw in lines:
		line = raw.strip()
		if not line or line.startswith("#"):
			continue

		name: Optional[str] = None
		email: Optional[str] = None

		match = NAME_EMAIL_PATTERN.match(line)
		if not match:
			match = NAME_DASH_EMAIL_PATTERN.match(line)
		if match:
			name = match.group("name").strip() or None
			email = match.group("email").strip()
		elif "," in line:
			name, email = _parse_csv_like(line)
		else:
			email = line

		if not email or not is_valid_email(email):
			continue
		contacts.append(
			Contact(
				name=name,
				email=email,
				affiliation=affiliation,
				source_url=source_url,
			)
		)
	return contacts


