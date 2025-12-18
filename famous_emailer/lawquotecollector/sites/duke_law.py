from __future__ import annotations

import time
from typing import List, Optional, Set
from urllib.parse import unquote

from bs4 import BeautifulSoup, Tag

from ..storage import Contact
from ..validators import is_valid_email
from ..scraper import _fetch_html


PAGE_DELAY_S = 1.0


def _extract_email(href: str) -> Optional[str]:
    if not href:
        return None
    lower = href.strip()
    if not lower.lower().startswith("mailto:"):
        return None
    addr = lower.split(":", 1)[1].split("?", 1)[0].strip()
    addr = unquote(addr)
    return addr or None


def _nearest_name(anchor: Tag) -> Optional[str]:
    # Prefer explicit name text (but avoid using the text of mailto buttons,
    # which often contains the literal "Email"). If the anchor itself is a
    # mailto link or its text is clearly a button label, search for nearby
    # headings such as h3.directory-name first.
    try:
        raw_text = (anchor.get_text(" ", strip=True) or "").strip()
    except Exception:
        raw_text = ""

    is_mailto_anchor = False
    try:
        href = (anchor.get("href") or "").strip().lower()
        if href.startswith("mailto:"):
            is_mailto_anchor = True
    except Exception:
        href = ""

    # Common button labels to ignore as names
    button_labels = {"email", "e-mail", "contact", "send email"}

    if raw_text and not is_mailto_anchor and raw_text.lower() not in button_labels and "@" not in raw_text and 1 <= len(raw_text.split()) <= 8:
        return raw_text

    # If this looks like a mailto or button, try to find a nearby h3.directory-name
    # within the current parent container or ancestors.
    container = anchor.parent
    checked = 0
    while container and isinstance(container, Tag) and checked < 6:
        # Prefer specific directory-name headings
        heading = container.select_one("h3.directory-name")
        if heading:
            htxt = (heading.get_text(" ", strip=True) or "").strip()
            if htxt and "@" not in htxt:
                return htxt

        # Generic heading fallback
        for h in container.find_all(["h1", "h2", "h3", "h4"], limit=2):
            t = (h.get_text(" ", strip=True) or "").strip()
            if t and "@" not in t and t.lower() not in button_labels:
                return t

        container = container.parent
        checked += 1

    # Final fallback: scan siblings of the original anchor for headings/strong text
    parent = anchor.parent
    if isinstance(parent, Tag):
        for sib in parent.find_all(["h1", "h2", "h3", "h4", "strong"], limit=4):
            t = (sib.get_text(" ", strip=True) or "").strip()
            if t and "@" not in t and t.lower() not in button_labels:
                return t

    return None


def _contacts_from_soup(soup: BeautifulSoup, page_url: str, affiliation: Optional[str]) -> List[Contact]:
    contacts: List[Contact] = []
    seen: Set[str] = set()

    # Typical Duke listing places names inside <h3 class="directory-name"><a ...>Name</a></h3>
    # Prefer those anchors, then fall back to profile-like hrefs.
    # First pass: find explicit name anchors within known heading
    profile_anchors: List[Tag] = []
    profile_anchors.extend(soup.select("h3.directory-name a"))
    profile_anchors.extend(soup.select("h3.directory-name"))
    # Also include profile link anchors as a last resort
    profile_anchors.extend(soup.select("a[href*='/fac/'], a[href*='/faculty/']"))

    # Normalize order and dedupe anchors by text+href
    unique_anchors: List[Tag] = []
    seen_anchor_keys: Set[str] = set()
    for a in profile_anchors:
        txt = (a.get_text(" ", strip=True) or "").strip()
        key = f"{txt.lower()}::{a.get('href','')}"
        if key in seen_anchor_keys:
            continue
        seen_anchor_keys.add(key)
        unique_anchors.append(a)

    for a in unique_anchors:
        # Prefer the text of the h3 anchor; if the element is an h3 (not an a),
        # extract its text.
        if a.name and a.name.lower() == "h3":
            name = (a.get_text(" ", strip=True) or "").strip()
        else:
            name = (a.get_text(" ", strip=True) or "").strip()
        if not name:
            name = _nearest_name(a) or ""

        # Search upward for a mailto link within the same logical block
        email = ""
        container = a if isinstance(a, Tag) else None
        depth = 0
        while container and isinstance(container, Tag) and depth < 6:
            mailto = container.select_one('a[href^="mailto:"]')
            if mailto:
                email = _extract_email(mailto.get("href", "")) or ""
                break
            container = container.parent
            depth += 1

        # If not found in ancestors, look at siblings following the nearest heading element
        if not email:
            # find a heading ancestor (h3) or use the parent of the anchor
            heading = a.find_parent("h3") or a.parent
            sib = heading.next_sibling if heading is not None else None
            steps = 0
            while sib and steps < 8:
                if isinstance(sib, Tag):
                    mailto = sib.select_one('a[href^="mailto:"]')
                    if mailto:
                        email = _extract_email(mailto.get("href", "")) or ""
                        break
                sib = sib.next_sibling
                steps += 1

        if email and not is_valid_email(email):
            email = ""

        dedupe_key = email.strip().lower() if email else f"name::{(name or '').strip().lower()}"
        if not dedupe_key or dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        contacts.append(Contact(name=name or None, email=email or "", affiliation=affiliation, source_url=page_url))

    # Fallback: if no contacts found above, try extracting mailto links and heuristics
    # Always also ensure we capture any mailto links that weren't associated above
    for a in soup.select('a[href^="mailto:"]'):
        email = _extract_email(a.get("href", "")) or ""
        if not email or not is_valid_email(email):
            continue
        key = email.strip().lower()
        if key in seen:
            continue
        # Try to find a name near the mailto anchor
        name = _nearest_name(a) or ""
        seen.add(key)
        contacts.append(Contact(name=name or None, email=email, affiliation=affiliation, source_url=page_url))

    return contacts


def parse_contacts(
    soup: BeautifulSoup,
    page_url: str,
    affiliation: Optional[str],
    source_url: Optional[str],
) -> List[Contact]:
    # Single-page listing usually; just parse current soup
    return _contacts_from_soup(soup, page_url, affiliation)


