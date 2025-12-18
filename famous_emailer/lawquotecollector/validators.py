import re

EMAIL_REGEX = re.compile(
	# Basic RFC5322-inspired pattern, strict enough for research use
	r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@([A-Za-z0-9-]+\.)+[A-Za-z]{2,}$"
)


def is_valid_email(email: str) -> bool:
	if not email:
		return False
	# Normalize and reject obvious redactions
	candidate = email.strip()
	if any(token in candidate.lower() for token in [" [at] ", "(at)", " [dot] ", "(dot)"]):
		return False
	return EMAIL_REGEX.match(candidate) is not None





