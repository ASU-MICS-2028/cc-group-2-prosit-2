# Translations

- `HealthConnect_English_Text.pdf` is what goes to the translator. It holds every piece of English the app shows, numbered, with an empty column for the translation.
- `healthconnect_text.csv` is the same text with each string's key (its name in `frontend/src/i18n.js`), so the returned translations can be copied into the app.

## Rebuild after the app's text changes

```
python3 docs/translations/extract_text.py   # i18n.js + SMS + server errors -> CSV
python3 docs/translations/make_pdf.py       # CSV -> PDF (needs: pip install reportlab)
```

## Mapping a translation back to the app

`pdf_numbers.csv` (written by `make_pdf.py`) lists each PDF number with its key, e.g. `42 → assess`. Put each returned translation against its key, then add the language as a new block in `i18n.js` (e.g. `ee: { ... }` for Ewe). Keys missing from the block fall back to English.

SMS text and server error messages are fixed English in the backend for now. Translating them only takes effect once the backend chooses a language per user.

## Machine draft (Google Translate), for review only

```
python3 docs/translations/make_pdf.py --new-only        # lists the untranslated lines
python3 docs/translations/machine_draft.py --dry-run    # shows the size and cost, sends nothing
python3 docs/translations/machine_draft.py              # writes machine_draft.csv
```

Needs `GOOGLE_TRANSLATE_API_KEY=...` in `backend/.env` (never commit it: the repo is public). Covers Twi, Ewe and Ga; Google has no Dagbani. The draft is a starting point for Isaac, not app text: medical wording is checked by a person before it goes into `i18n.js`. The script runs once, offline from the app, so the key never reaches users' phones.
