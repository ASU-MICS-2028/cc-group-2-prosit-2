# Languages and translation (Phase 6)

HealthConnect is used by CHVs and patients who may not read English well. This note records which Ghanaian languages the app supports, how the text was translated, and why we chose human translation over a live translation API.

## What is built

- The app's screens are in **English, Twi, Ewe, Ga and Dagbani**, chosen from a dropdown on the sign-in page and in the top bar.
- All screen text lives in `frontend/src/i18n.js`. Any string without a translation falls back to English.
- Isaac Ansah Amoah translated the text from a numbered English sheet. The tools in `docs/translations/` make that sheet straight from the code.
- Coverage: 245 strings in each language, reviewed by native speakers. The app now has 314 English strings: the 60 pharmacy and System health labels added later are not translated yet. Seven older strings also stay English until they are translated again: "Check risk", "Visit history", "No checks recorded yet.", "Book follow-up", "Booked for", "Booked by", and the appointment reason hint.
- The SMS messages and server error messages are translated too (`docs/translations/healthconnect_text.csv`), but the app does not send them in other languages yet (see below).

## Translation APIs compared

Checked on 5 November 2026 against each provider's published language list.

| Service | Twi | Ewe | Ga | Dagbani | Works offline | Patient data leaves the app |
|---|---|---|---|---|---|---|
| GhanaNLP Khaya | Yes* | Yes* | Yes* | Yes* | No | Yes (Ghana-based provider) |
| Google Cloud Translation | Yes (code `ak`) | Yes | Yes | **No** | No | Yes (Google servers abroad) |
| Amazon Translate (AWS) | No | No | No | No | No | n/a |
| Azure Translator (Microsoft) | No | No | No | No | No | n/a |
| Human translation in `i18n.js` (what we use) | Yes | Yes | Yes | Yes | **Yes** | **No** |

\* From the Khaya SDK documentation, not checked against GhanaNLP's own documentation.

**Accuracy:** machine translation for these languages is still weak, especially for medical words and short button labels without context. A wrong word on a health app can cause harm, e.g. a symptom or a danger sign misread.

**Cost:** an API charges per character on every use. Fixed text translated once by a person costs nothing to serve.

**Privacy:** the Ghana Data Protection Act, 2012 (Act 843) requires data minimisation and purpose limitation. Sending patient notes to an outside translation service shares health data with a third party, often outside Ghana.

## Recommendation

1. **Fixed text (screens, SMS templates, error messages): human translation, stored in the app.** It works offline, costs nothing per use, never sends patient data anywhere, and a speaker can check it. This is what is built.
2. **No live machine translation of patient data.** Names, notes and symptoms are never sent to a translation API.
3. **If live translation is needed later** (e.g. a CHV's free-text note for a doctor who speaks another language): try **GhanaNLP Khaya** first, since it covers all four languages and is based in Ghana. Use it only on text with no names or identifiers, and with the patient's consent. Google covers Twi, Ewe and Ga but not Dagbani. AWS, our cloud provider, covers none of them.

## Next steps

- **Translated SMS:** add a "preferred language" field when a CHV registers a patient. Then send the appointment SMS in that language using Isaac's translations.
- **Native-speaker review: done.** The translations were reviewed by native speakers. Strings added later (pharmacy, System health) still need translating and reviewing.
- **Remember the language:** the app goes back to English when the page reloads. Save the choice on the phone.
