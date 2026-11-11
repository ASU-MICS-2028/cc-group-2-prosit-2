"""Extract every English string users see into one CSV for translators.

Run from the repo root:  python docs/translations/extract_text.py
Re-run whenever i18n.js changes; translations already typed into the CSV are kept.
"""
import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "frontend" / "src"
OUT = Path(__file__).parent / "healthconnect_text.csv"
LANGUAGES = ["Twi", "Ewe", "Ga", "Dagbani"]

# Which screen each React file is, in words a translator understands
SCREENS = {
    "Login.jsx": "Sign-in page",
    "Header.jsx": "Top bar (all users)",
    "App.jsx": "App frame (all users)",
    "ChvApp.jsx": "CHV: patient list and registration",
    "PatientDetail.jsx": "CHV: patient page",
    "GeneralVisitForm.jsx": "CHV: general visit form",
    "AntenatalForm.jsx": "CHV: antenatal check form",
    "ConditionChips.jsx": "Possible conditions (CHV, nurse, doctor)",
    "RiskBadge.jsx": "Risk label (CHV, nurse, doctor)",
    "PatientHistory.jsx": "Patient history (nurse, doctor)",
    "InboxApp.jsx": "Nurse/doctor: referral inbox",
    "AppointmentsPanel.jsx": "Appointments (nurse, doctor)",
    "VideoCall.jsx": "Video call",
    "IncomingCalls.jsx": "Video call: incoming call",
    "GhsApp.jsx": "GHS officer: surveillance dashboard",
    "DistrictMap.jsx": "GHS officer: district map",
    "AdminApp.jsx": "System admin: staff accounts",
    "SystemHealthPanel.jsx": "System admin: system health",
    "ReminderPreference.jsx": "CHV: patient list and registration",
    "HealerPanel.jsx": "Community: traditional healer referrals (CHV)",
    "InsurancePanel.jsx": "Community: health insurance (CHV, nurse, doctor)",
    "LessonsPanel.jsx": "Community: health education lessons",
    "LessonSlides.jsx": "Community: health education lessons",
    "TrainingPanel.jsx": "Community: health worker training",
    "FeePayment.jsx": "Community: fees and payments",
    "FacilityPanel.jsx": "Facility: manager tools (nurse, doctor)",
    "EquipmentPanel.jsx": "Facility: equipment",
    "ImpactPanel.jsx": "GHS officer: SDG 3 progress",
    "PharmacistApp.jsx": "Pharmacist: pharmacy",
    "Prescriptions.jsx": "Doctor and pharmacist: prescriptions",
    "StockOutsPanel.jsx": "GHS officer: medicine shortages",
    "ChangePassword.jsx": "Change password (first sign-in)",
    "SavedCopyNote.jsx": "Offline note (all users)",
    "ImmunisationPanel.jsx": "CHV: child vaccinations (GHS sees totals)",
    "SurveyPanel.jsx": "CHV: household survey (GHS sees totals)",
    "CommunityAlertPanel.jsx": "GHS officer: community health alert SMS",
    "main.jsx": "App start-up",
}

# SMS and server messages are not in i18n.js, so they are listed here by hand.
# Keep {placeholders} exactly as they are: the app fills them in.
SMS = [
    ("sms_appt_confirm", "SMS to patient (backend/reminders.py)",
     "HealthConnect: Your appointment is booked at {facility} on {date and time}. Ref {ref}. Please come on time."),
    ("sms_appt_reminder", "SMS to patient (backend/reminders.py)",
     "HealthConnect: Reminder: you have an appointment at {facility} on {date and time}. Ref {ref}. Please come on time."),
    ("sms_referral", "SMS to facility staff (backend/main.py)",
     "HealthConnect Referral / Ref / Age / Visit: Antenatal or General / Risk / Check for / CHV / "
     "Please prepare to receive this patient."),
]


def read_english():
    """Return [(key, english)] from the en block of i18n.js, in file order."""
    lines = (SRC / "i18n.js").read_text(encoding="utf-8").splitlines()
    pairs, inside = [], False
    for line in lines:
        if line.strip() == "en: {":
            inside = True
        elif inside and line.strip() == "},":
            break
        elif inside:
            match = re.match(r'\s+(\w+): (".*"),$', line)
            if match:
                pairs.append((match.group(1), json.loads(match.group(2))))  # json undoes \" escapes
    return pairs


def read_twi():
    """Return {key: twi} from the tw block, so Isaac sees what already exists."""
    block = (SRC / "i18n.js").read_text(encoding="utf-8").split("tw: {")[1].split("},")[0]
    return {k: json.loads(v) for k, v in re.findall(r'(\w+): (".*"),', block)}


def read_server_errors():
    """Return [(key, where, english)] for every HTTPException(detail="...") in the backend."""
    rows = []
    for file in sorted((ROOT / "backend").glob("*.py")):
        for message in re.findall(r'detail="([^"]+)"', file.read_text(encoding="utf-8")):
            if message not in [r[2] for r in rows]:  # same message in two places = translate once
                key = "err_" + re.sub(r"\W+", "_", message.lower()).strip("_")[:40]  # from the text, so it never shifts
                rows.append((key, f"Error shown to staff (backend/{file.name})", message))
    return rows


def screens_for(key, sources):
    """Find which React files use this key, directly (t.key) or by prefix (t["cond_" + c])."""
    prefix = key.split("_")[0] + "_" if "_" in key else None
    found = []
    for name, code in sources.items():
        direct = re.search(rf"\bt\.{key}\b", code)
        by_prefix = prefix and f't["{prefix}"' in code
        by_name = re.search(r"t\[[\w.]+\]", code) and f'"{key}"' in code  # e.g. t[name] in a field list
        if direct or by_prefix or by_name:
            found.append(SCREENS.get(name, name))
    return "; ".join(found) or "Not found in screens (check before translating)"


def main():
    sources = {f.name: f.read_text(encoding="utf-8") for f in SRC.glob("*.jsx")}
    twi = read_twi()

    # Keep translations Isaac has already typed, so re-running never loses work
    old = {}
    if OUT.exists():
        with OUT.open(encoding="utf-8-sig") as f:
            old = {row["key"]: row for row in csv.DictReader(f)}

    rows = [(key, screens_for(key, sources), english) for key, english in read_english()]
    rows += SMS + read_server_errors()

    with OUT.open("w", newline="", encoding="utf-8-sig") as f:  # utf-8-sig: Excel shows Ɔ, ɛ correctly
        writer = csv.writer(f)
        writer.writerow(["key", "where it appears", "English"] + LANGUAGES + ["notes"])
        for key, where, english in rows:
            previous = old.get(key, {})
            translations = [previous.get(lang) or (twi.get(key, "") if lang == "Twi" else "")
                            for lang in LANGUAGES]
            writer.writerow([key, where, english] + translations + [previous.get("notes", "")])
    print(f"Wrote {len(rows)} strings to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
