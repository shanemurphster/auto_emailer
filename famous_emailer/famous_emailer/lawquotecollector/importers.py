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

		# Try known patterns first: "Name <email>" and "Name - email" (various dashes)
		match = NAME_EMAIL_PATTERN.match(line)
		if not match:
			match = NAME_DASH_EMAIL_PATTERN.match(line)
		if match:
			name = match.group("name").strip() or None
			email = match.group("email").strip()
		elif "," in line:
			# CSV-like "name,email" or "email,name"
			name, email = _parse_csv_like(line)
		else:
			# General heuristics:
			# 1) Look for an email-like token anywhere in the line.
			# 2) If found, take the nearest reasonable name text from the left side.
			# 3) Clean surrounding punctuation.
			EMAIL_TOKEN_RE = re.compile(r'([A-Za-z0-9.!#$%&\'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})')
			m = EMAIL_TOKEN_RE.search(line)
			if m:
				email_candidate = m.group(1).strip().rstrip('.,;:')
				if is_valid_email(email_candidate):
					email = email_candidate
					# name is the line with the email removed
					left = (line[: m.start()].strip() or line[m.end():].strip())
					# If left is empty, try splitting on dash to the right side instead
					if not left:
						parts = re.split(r"\s*[-\u2012\u2013\u2014]\s*", line, maxsplit=1)
						if len(parts) == 2:
							left = parts[0].strip() or parts[1].strip()
					# Clean trailing punctuation and bracketed notes
					left = re.sub(r'^[\u2018\u2019"\']+|[\u2018\u2019"\']+$', '', left).strip()
					left = re.sub(r'[\(\[\{].*?[\)\]\}]$', '', left).strip()
					# If left contains a separator like " - " or " – ", split and take the non-email side
					parts = re.split(r"\s*[-\u2012\u2013\u2014]\s*", left, maxsplit=1)
					if len(parts) == 2:
						# choose the most name-like side (prefer side without @)
						side0 = parts[0].strip()
						side1 = parts[1].strip()
						name_candidate = side0 if '@' not in side0 else side1
						name = name_candidate or None
					else:
						# If left still contains commas like "Last, First", keep as-is
						name = left or None
			else:
				# No email token found: try dash-split fallback "Name - emaillike" where rhs may be noisy
				parts = re.split(r"\s*[-\u2012\u2013\u2014]\s*", line, maxsplit=1)
				if len(parts) == 2:
					right = parts[1].strip().rstrip('.,;:')
					if is_valid_email(right):
						name = parts[0].strip() or None
						email = right
					else:
						# maybe reversed order "email - name"
						left = parts[0].strip().rstrip('.,;:')
						if is_valid_email(left):
							email = left
							name = parts[1].strip() or None
						else:
							# last resort: nothing parsed here
							email = None
				else:
					email = None

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


