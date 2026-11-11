"""Prescription codes and fraud/safety rules (no database code here, so each rule is easy to read).

Fake and forged prescriptions, the same prescription filled at several pharmacies, and misuse of
tramadol are real problems in Ghana. The checks:
  1. Every prescription has a random code: it cannot be guessed or made up.
  2. It can be dispensed ONCE, at our pharmacy or any outside pharmacy, and only before it expires.
  3. Quantity limits per drug: a typo (150 instead of 15) or an "extra" quantity is refused.
  4. Controlled drugs (misuse risk): a written reason is required, they expire after 7 days,
     and a doctor writing many of them in a week is flagged to GHS.
  5. The same drug for the same patient within 14 days needs a reason (duplicate).
  6. Many wrong codes from one internet address = someone guessing: blocked and flagged.

The numbers below are examples for the demo, not GHS or Pharmacy Council guidance.
"""
import secrets

# 32 letters and digits, without 0/O and 1/I/L, which are easy to misread on paper or over the phone
ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
CODE_LENGTH = 8  # 31^8 = about 850 billion possible codes

VALID_DAYS = 30
CONTROLLED_VALID_DAYS = 7
DUPLICATE_DAYS = 14
HIGH_VOLUME_CONTROLLED = 5  # controlled-drug prescriptions by one doctor in 7 days before GHS is told
WRONG_CODES_PER_HOUR = 10   # per internet address

CONTROLLED = {"Tramadol 50 mg capsule", "Diazepam 5 mg tablet"}

# Most one prescription may hold; anything else: 100
MAX_QUANTITY = {
    "Artemether-lumefantrine 20/120 mg tablets (pack of 24)": 2,
    "Sulfadoxine-pyrimethamine 500/25 mg tablet (IPTp)": 3,
    "Malaria rapid diagnostic test (RDT)": 2,
    "Cholera rapid diagnostic test": 2,
    "Oral rehydration salts (ORS) sachet": 20,
    "Zinc 20 mg dispersible tablet": 14,
    "Amoxicillin 250 mg dispersible tablet": 40,
    "Ceftriaxone 1 g injection": 14,
    "Vitamin A 200,000 IU capsule": 2,
    "Methyldopa 250 mg tablet": 120,
    "Nifedipine 20 mg tablet": 60,
    "Magnesium sulphate 50% injection (5 g in 10 ml)": 12,
    "Paracetamol 500 mg tablet": 60,
    "Ferrous sulphate + folic acid tablet": 90,
    "Oxytocin 10 IU injection": 3,
    "Tramadol 50 mg capsule": 20,
    "Diazepam 5 mg tablet": 10,
}
DEFAULT_MAX = 100


def new_code():
    """e.g. '7KQ4M9TX'. secrets (not random) because the code is the patient's key to the drugs."""
    return "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))


def clean_code(text):
    """What a pharmacist types: '7kq4-m9tx ' -> '7KQ4M9TX'. None if it cannot be a code."""
    code = "".join(ch for ch in str(text).upper() if ch.isalnum())
    return code if len(code) == CODE_LENGTH and all(ch in ALPHABET for ch in code) else None


def show_code(code):
    """'7KQ4M9TX' -> '7KQ4-M9TX' (easier to read out)."""
    return f"{code[:4]}-{code[4:]}" if code else None


def max_quantity(drug_name):
    return MAX_QUANTITY.get(drug_name, DEFAULT_MAX)


def initials(full_name):
    """'Adwoa Boateng' -> 'A. B.': enough for an outside pharmacy to check, without the full name."""
    return " ".join(part[0].upper() + "." for part in full_name.split() if part)
