"""Machine-translate the untranslated lines with Google Translate, as a DRAFT for Isaac to review.

Run from the repo root, after make_pdf.py --new-only:
    python3 docs/translations/machine_draft.py --dry-run   # count only, no cost
    python3 docs/translations/machine_draft.py             # translate

Needs GOOGLE_TRANSLATE_API_KEY in backend/.env (never commit it: the repo is public).
Writes machine_draft.csv. The app never uses this file directly: medical wording must be
checked by a person before it reaches the app. Dagbani is left empty: Google does not support it.
"""
import csv
import html
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
SOURCE = HERE / "pdf_numbers_new.csv"  # the untranslated lines, numbered as in the PDF Isaac gets
OUT = HERE / "machine_draft.csv"
GOOGLE_CODES = {"Twi": "ak", "Ewe": "ee", "Ga": "gaa"}  # Dagbani: not in Google Translate
URL = "https://translation.googleapis.com/language/translate/v2"
BATCH = 100  # Google accepts up to 128 lines per request


def read_key():
    """The key from the environment, or from backend/.env (git ignores it)."""
    if os.environ.get("GOOGLE_TRANSLATE_API_KEY"):
        return os.environ["GOOGLE_TRANSLATE_API_KEY"]
    for env in (ROOT / "backend" / ".env", ROOT / ".env"):
        if env.exists():
            for line in env.read_text().splitlines():
                if line.startswith("GOOGLE_TRANSLATE_API_KEY="):
                    return line.split("=", 1)[1].strip().strip("\"'")
    sys.exit("No GOOGLE_TRANSLATE_API_KEY in backend/.env")


def protect(text):
    """Wrap {placeholders} so Google leaves them alone (the app fills them in)."""
    return re.sub(r"(\{\w+\})", r'<span translate="no">\1</span>', html.escape(text))


def unprotect(text):
    return html.unescape(re.sub(r'<span translate="no">\s*(\{\w+\})\s*</span>', r"\1", text))


def translate(lines, target, key):
    """Send lines to Google in batches; return the translations in the same order."""
    result = []
    for start in range(0, len(lines), BATCH):
        body = json.dumps({"q": [protect(s) for s in lines[start:start + BATCH]],
                           "source": "en", "target": target, "format": "html"}).encode()
        request = urllib.request.Request(f"{URL}?key={key}", data=body,
                                         headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                data = json.load(response)
        except urllib.error.HTTPError as err:
            sys.exit(f"Google said {err.code}: {err.read().decode()[:300]}")
        result += [unprotect(t["translatedText"]) for t in data["data"]["translations"]]
    return result


def main(dry_run=False):
    with SOURCE.open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    lines = [r["English"] for r in rows]
    chars = sum(map(len, lines)) * len(GOOGLE_CODES)
    print(f"{len(lines)} lines x {len(GOOGLE_CODES)} languages = {chars:,} characters "
          f"(about ${chars * 20 / 1_000_000:.2f}; first 500,000 a month are free)")
    if dry_run:
        return

    key = read_key()
    drafts = {lang: translate(lines, code, key) for lang, code in GOOGLE_CODES.items()}

    with OUT.open("w", newline="", encoding="utf-8-sig") as f:  # utf-8-sig: Excel shows Ɔ, ɛ
        writer = csv.writer(f)
        writer.writerow(["No.", "key", "English", "Twi (machine)", "Ewe (machine)", "Ga (machine)",
                         "Dagbani", "reviewed by Isaac"])
        for i, r in enumerate(rows):
            writer.writerow([r["No."], r["key"], r["English"]]
                            + [drafts[lang][i] for lang in GOOGLE_CODES] + ["", ""])
    print(f"Wrote {OUT.relative_to(ROOT)}: a DRAFT. Isaac must review it before it goes into i18n.js.")


if __name__ == "__main__":
    main(dry_run="--dry-run" in sys.argv)
