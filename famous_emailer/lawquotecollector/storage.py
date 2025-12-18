from __future__ import annotations

import csv
import logging
import os
import sqlite3
from dataclasses import dataclass, asdict
from typing import Iterable, List, Optional


@dataclass
class Contact:
	name: str | None
	email: str
	affiliation: str | None
	source_url: str | None


CSV_HEADERS = ["name", "email", "affiliation", "source_url"]

logger = logging.getLogger(__name__)


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


def save_names_csv(path: str, names: Iterable[str], affiliation: Optional[str] = None, source_url: Optional[str] = None, overwrite: bool = False) -> int:
	"""
	Write name-only rows to a CSV at `path`. Each row will have `name` populated and
	`email` left empty. If `overwrite` is True the file will be replaced; otherwise
	the names will be appended (or file created).
	Returns number of rows written.
	"""
	ensure_parent_dir(path)
	mode = "w" if overwrite or not os.path.exists(path) else "a"
	count = 0
	with open(path, mode, newline="", encoding="utf-8") as f:
		writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
		if mode == "w":
			writer.writeheader()
		for n in names:
			name = (n or "").strip()
			if not name:
				continue
			row = {"name": name, "email": "", "affiliation": affiliation or "", "source_url": source_url or ""}
			writer.writerow(row)
			count += 1
	return count


def update_names_in_csv(path: str, contacts: Iterable[Contact]) -> int:
	"""
	Update the `name` column in an existing CSV at `path` by matching emails.
	For each contact provided, if a row exists with the same email (case-insensitive),
	and the contact has a non-empty name, replace the row's `name` value.
	Returns the number of rows updated.
	"""
	logger.info(f"Starting update_names_in_csv for file: {path}")
	contacts_list = list(contacts)
	logger.info(f"Received {len(contacts_list)} contacts to process")

	if not os.path.exists(path):
		logger.error(f"CSV file does not exist: {path}")
		raise FileNotFoundError(path)

	# Build map email -> name from provided contacts (prefer first occurrence)
	email_to_name: dict[str, str] = {}
	for c in contacts_list:
		logger.debug(f"Processing contact: email='{c.email}', name='{c.name}'")
		if c.email and c.name:
			key = c.email.strip().lower()
			if key and key not in email_to_name:
				email_to_name[key] = c.name.strip()
				logger.debug(f"Added mapping: {key} -> '{c.name.strip()}'")

	logger.info(f"Built {len(email_to_name)} email-to-name mappings from contacts")
	if not email_to_name:
		logger.warning("No valid email-to-name mappings found in provided contacts")

	updated = 0
	rows = []
	total_rows = 0
	matched_emails = 0

	with open(path, "r", newline="", encoding="utf-8") as rf:
		reader = csv.DictReader(rf)
		fieldnames = reader.fieldnames or CSV_HEADERS
		for row in reader:
			total_rows += 1
			em = (row.get("email") or "").strip().lower()
			current_name = (row.get("name") or "").strip()

			if em and em in email_to_name:
				matched_emails += 1
				new_name = email_to_name[em]
				logger.debug(f"Found match for email '{em}': current_name='{current_name}', new_name='{new_name}'")
				if current_name != new_name:
					row["name"] = new_name
					updated += 1
					logger.debug(f"Updated row {total_rows}: '{current_name}' -> '{new_name}'")
				else:
					logger.debug(f"No update needed for row {total_rows}: name already matches")
			rows.append(row)

	logger.info(f"Processed {total_rows} rows from CSV, found {matched_emails} email matches, updated {updated} rows")

	# Write back updated CSV (overwrite with backup)
	backup = f"{path}.bak"
	os.replace(path, backup)
	with open(path, "w", newline="", encoding="utf-8") as wf:
		writer = csv.DictWriter(wf, fieldnames=fieldnames)
		writer.writeheader()
		for row in rows:
			out = {k: row.get(k, "") for k in fieldnames}
			writer.writerow(out)

	logger.info(f"Successfully wrote updated CSV to {path}")
	return updated


def fill_names_by_order(path: str, names: Iterable[str], affiliation_contains: Optional[str] = None, max_fill: Optional[int] = None) -> int:
	"""
	Fill empty `name` fields in CSV rows whose `affiliation` contains `affiliation_contains`
	(or all rows if affiliation_contains is None), using names from the provided iterable in order.
	Returns number of rows updated.
	"""
	logger.info(f"Starting fill_names_by_order for file: {path}")
	logger.info(f"Affiliation filter: '{affiliation_contains}', max_fill: {max_fill}")

	names_list = [n.strip() for n in names if n and n.strip()]
	logger.info(f"Received {len(names_list)} names to fill")
	if names_list:
		logger.debug(f"Names to fill: {names_list[:5]}{'...' if len(names_list) > 5 else ''}")

	if not os.path.exists(path):
		logger.error(f"CSV file does not exist: {path}")
		raise FileNotFoundError(path)

	if not names_list:
		logger.warning("No valid names provided to fill")
		return 0

	name_idx = 0
	updated = 0
	rows = []
	total_rows = 0
	filtered_rows = 0
	empty_name_rows = 0

	with open(path, "r", newline="", encoding="utf-8") as rf:
		reader = csv.DictReader(rf)
		fieldnames = reader.fieldnames or CSV_HEADERS
		for row in reader:
			total_rows += 1
			current_name = (row.get("name") or "").strip()
			affiliation = (row.get("affiliation") or "").strip()

			# check filter
			if affiliation_contains:
				aff_lower = affiliation.lower()
				if affiliation_contains.lower() not in aff_lower:
					logger.debug(f"Row {total_rows} filtered out: affiliation '{affiliation}' doesn't contain '{affiliation_contains}'")
					rows.append(row)
					continue
				filtered_rows += 1

			# check if name is empty
			if not current_name:
				empty_name_rows += 1
				logger.debug(f"Row {total_rows} has empty name, affiliation: '{affiliation}'")

			# fill if empty name and we still have names
			if not current_name and name_idx < len(names_list):
				row["name"] = names_list[name_idx]
				logger.info(f"Filled row {total_rows}: empty name -> '{names_list[name_idx]}' (affiliation: '{affiliation}')")
				name_idx += 1
				updated += 1

				if max_fill and updated >= max_fill:
					logger.info(f"Reached max_fill limit ({max_fill}), stopping after filling {updated} names")
					rows.append(row)
					# append remaining rows unchanged
					for rem in reader:
						rows.append(rem)
					break
			rows.append(row)

	logger.info(f"Processed {total_rows} rows total")
	if affiliation_contains:
		logger.info(f"Rows matching affiliation filter: {filtered_rows}")
	logger.info(f"Rows with empty names: {empty_name_rows}")
	logger.info(f"Names filled: {updated} (used {name_idx} out of {len(names_list)} available names)")

	if name_idx < len(names_list):
		logger.warning(f"Not all names were used: {len(names_list) - name_idx} names remaining")
	if name_idx == len(names_list):
		logger.info("All available names were used")

	# write backup and new CSV
	backup = f"{path}.bak"
	os.replace(path, backup)
	with open(path, "w", newline="", encoding="utf-8") as wf:
		writer = csv.DictWriter(wf, fieldnames=fieldnames)
		writer.writeheader()
		for row in rows:
			out = {k: row.get(k, "") for k in fieldnames}
			writer.writerow(out)

	logger.info(f"Successfully wrote updated CSV to {path}")
	return updated



