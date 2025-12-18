from __future__ import annotations

from typing import Callable, List, Optional
from bs4 import BeautifulSoup

from ..storage import Contact


# Parser signature: returns contacts found in the given page soup
ParserFunc = Callable[[BeautifulSoup, str, Optional[str], Optional[str]], List[Contact]]


_REGISTRY: dict[str, ParserFunc] = {}


def register(site_key: str, parser: ParserFunc) -> None:
	_REGISTRY[site_key] = parser


def get(site_key: Optional[str]) -> ParserFunc:
	from .generic import parse_contacts as generic_parser  # lazy import
	if not site_key:
		return generic_parser
	return _REGISTRY.get(site_key, generic_parser)

# Register built-in site parsers
try:
	from . import harvard_law as _harvard_law
	register("harvard", _harvard_law.parse_contacts)
except Exception:
	# Optional: if import fails, keep registry minimal
	pass

try:
	from . import yale_law as _yale_law
	register("yale", _yale_law.parse_contacts)
except Exception:
	pass

try:
	from . import columbia_law as _columbia_law
	register("columbia", _columbia_law.parse_contacts)
except Exception:
	pass

try:
	from . import stanford_law as _stanford_law
	register("stanford", _stanford_law.parse_contacts)
except Exception:
	pass

try:
	from . import pennstate_law as _pennstate_law
	register("pennstate", _pennstate_law.parse_contacts)
except Exception:
	pass

try:
	from . import duke_law as _duke_law
	register("duke", _duke_law.parse_contacts)
except Exception:
	pass

try:
	from . import uchicago_law as _uchicago_law
	# allow both 'uchicago' and 'uchicago_law' keys
	register("uchicago", _uchicago_law.parse_contacts)
	register("uchicago_law", _uchicago_law.parse_contacts)
except Exception:
	pass

try:
	from . import nyu_law as _nyu_law
	register("nyu", _nyu_law.parse_contacts)
except Exception:
	pass


