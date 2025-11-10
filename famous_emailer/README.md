## LawQuoteCollector

An ethical research tool to collect publicly available contact information for law professors and legal scholars, then generate personalized Gmail drafts requesting a short quote for a student book project.

### Key principles
- Only parse visible, public information (names, emails, affiliations) on university pages that allow crawling. Respect robots.txt and site terms.
- Crawl lightly: identify the bot via User-Agent, honor `robots.txt`, apply timeouts, and avoid rapid-fire requests.
- Store data locally. Draft emails are created but never auto-sent.

### Project structure
- `lawquotecollector/` – Python scraper, validators, storage, CLI
- `data/` – Local outputs (default `data/law_contacts.csv`)
- `apps_script/CreateDrafts.gs` – Google Apps Script to generate Gmail drafts from a Google Sheet

### Requirements
- Python 3.11+
- `pip install -r requirements.txt`

### Quick start
1) Create a virtual environment (recommended)
```bash
python -m venv .venv
. .venv/Scripts/activate  # Windows PowerShell: . .venv/Scripts/Activate.ps1
pip install -r requirements.txt
```

2) Scrape site-specific directories to CSV
```bash
# Yale (emails on listing pages; paginates ?page=N)
python main.py scrape "https://law.yale.edu/faculty?page=0" \
  --site yale \
  --affiliation "Yale Law School" \
  --out data/law_contacts.csv --format csv --append

# Columbia (emails on listing pages; paginates ?page=N)
python main.py scrape "https://www.law.columbia.edu/faculty-and-scholarship/all-faculty?page=0" \
  --site columbia \
  --affiliation "Columbia Law School" \
  --out data/law_contacts.csv --format csv --append

# Harvard (profiles hold emails; parser visits each profile)
python main.py scrape "<HARVARD_DIRECTORY_URL>" \
  --site harvard \
  --affiliation "Harvard Law School" \
  --out data/law_contacts.csv --format csv --append
```

Notes:
- Respects `robots.txt` and uses polite delays.
- Extracts `mailto:` addresses; missing emails are skipped.
- Duplicates are skipped across runs by email.

3) Optional: Save to SQLite instead of CSV
```bash
python main.py scrape "https://law.yale.edu/faculty?page=0" \
  --site yale \
  --affiliation "Yale Law School" \
  --out data/law_contacts.db --format sqlite
```

4) Import a manual email list
```bash
python main.py import-list --input emails.txt \
  --affiliation "Independent Research" \
  --source-url "manual_compilation" \
  --out data/law_contacts.csv --format csv --append
```

`emails.txt` can contain lines in any of these formats (blank lines and `#` comments are ignored):
- `prof@example.edu`
- `Professor Name <prof@example.edu>`
- `Professor Name, prof@example.edu` or `prof@example.edu, Professor Name`
- `Professor Name - prof@example.edu`

### Supported columns
The CSV/Sheet schema is: `name,email,affiliation,source_url`. Optional columns like `subject`/`area_of_law`/`area` will personalize drafts.

### Generate Gmail drafts (Google Apps Script)
Recommended approach: import your CSV to a Google Sheet, then use the provided Apps Script to create drafts.

Steps:
1) In Google Drive, create a Google Sheet named `LawContacts` with headers:
   - `name`, `email`, `affiliation`, `source_url`
   - Import `data/law_contacts.csv` into this sheet.
2) In the Sheet, open Extensions → Apps Script. Create a script file and paste `apps_script/CreateDrafts.gs` contents.
3) Adjust the email template in the script as needed (subject/body placeholders).
4) Run `LawQuoteCollector → Create Drafts` from the sheet menu. Review drafts in Gmail before sending.

### Ethical usage checklist
- Confirm the target site permits crawling (robots.txt and terms).
- Only collect visible public contacts (no guessing, no hidden content, no paid databases).
- Rate-limit yourself and limit scope to what you need.
- Provide a clear purpose in outreach and make opting out easy.

### Troubleshooting
- If no results are found, the directory may not use `mailto:` links or content may be JS-rendered. Consider manual export or using a site-specific parser.
- If `robots.txt` denies the page, the tool will exit rather than scrape.
- For dynamic sites, consider Playwright in the future; this tool currently uses `requests` + `BeautifulSoup` only.

### License
For educational/research use. Verify your institution's policies before use.


