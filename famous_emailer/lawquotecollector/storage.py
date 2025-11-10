from __future__ import annotations

import csv
import os
import sqlite3
from dataclasses import dataclass, asdict
from typing import Iterable, List


@dataclass
class Contact:
	name: str | None
	email: str
	affiliation: str | None
	source_url: str | None


CSV_HEADERS = ["name", "email", "affiliation", "source_url"]


def ensure_parent_dir(path: str) -> None:
	parent = os.path.dirname(os.path.abspath(path))
	if parent and not os.path.exists(parent):
		os.makedirs(parent, exist_ok=True)


def dedupe_contacts(contacts: Iterable[Contact]) -> List[Contact]:
	seen = set()
	unique: List[Contact] = []
	for c in contacts:
		key = (c.email.strip().lower())
		if key in seen:
			continue
		seen.add(key)
		unique.append(c)
	return unique


def save_contacts_csv(path: str, contacts: Iterable[Contact], append: bool = True) -> int:
	ensure_parent_dir(path)
	mode = "a" if append and os.path.exists(path) else "w"
	# If appending, load existing emails to avoid duplicates across runs
	existing_emails = set()
	if mode == "a":
		try:
			with open(path, "r", newline="", encoding="utf-8") as rf:
				reader = csv.DictReader(rf)
				for row in reader:
					em = (row.get("email") or "").strip().lower()
					if em:
						existing_emails.add(em)
		except FileNotFoundError:
			pass

	count = 0
	with open(path, mode, newline="", encoding="utf-8") as f:
		writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
		if mode == "w":
			writer.writeheader()
		for c in contacts:
			em_key = c.email.strip().lower()
			if em_key in existing_emails:
				continue
			writer.writerow(asdict(c))
			existing_emails.add(em_key)
			count += 1
	return count


def save_contacts_sqlite(path: str, contacts: Iterable[Contact]) -> int:
	ensure_parent_dir(path)
	conn = sqlite3.connect(path)
	try:
		cur = conn.cursor()
		cur.execute(
			"""
			CREATE TABLE IF NOT EXISTS law_contacts (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				name TEXT,
				email TEXT UNIQUE,
				affiliation TEXT,
				source_url TEXT
			)
			"""
		)
		inserted = 0
		for c in contacts:
			try:
				cur.execute(
					"INSERT OR IGNORE INTO law_contacts(name, email, affiliation, source_url) VALUES (?,?,?,?)",
					(c.name, c.email, c.affiliation, c.source_url),
				)
				if cur.rowcount:
					inserted += 1
			except sqlite3.IntegrityError:
				pass
		conn.commit()
		return inserted
	finally:
		conn.close()



