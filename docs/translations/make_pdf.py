"""Turn healthconnect_text.csv into a printable PDF for the translator.

Run after extract_text.py:  python docs/translations/make_pdf.py   (needs: pip install reportlab)
Only lines not translated yet:  python docs/translations/make_pdf.py --new-only
Numbers in the PDF follow the same order every run, so a translation "No. 42" maps back to one key.
"""
import csv
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from xml.sax.saxutils import escape

HERE = Path(__file__).parent
CSV_FILE = HERE / "healthconnect_text.csv"
PDF_FILE = HERE / "HealthConnect_English_Text.pdf"
NEW_PDF_FILE = HERE / "HealthConnect_New_Text.pdf"
LANGUAGES = ["Twi", "Ewe", "Ga", "Dagbani"]
# Team decision: these stay in English, so they are never sent for translation again
KEEP_ENGLISH = {"assess", "history", "noHistory", "bookFollowUp", "bookedFor", "bookedBy", "apptReasonPlaceholder"}

# Arial has the accented and Twi letters a translator may type back
FONTS = "/System/Library/Fonts/Supplemental/"
pdfmetrics.registerFont(TTFont("Arial", FONTS + "Arial.ttf"))
pdfmetrics.registerFont(TTFont("Arial-Bold", FONTS + "Arial Bold.ttf"))

# Sections in the order a user meets them; a string goes to the section of the first screen it is on
SECTIONS = [
    ("Signing in and passwords", ["Sign-in page", "Change password"]),
    ("Seen by all users", ["Top bar", "App frame", "Offline note", "App start-up"]),
    ("Community Health Volunteer (CHV) screens", ["CHV:", "Possible conditions", "Risk label"]),
    ("Nurse and doctor screens", ["Nurse/doctor", "Appointments", "Patient history"]),
    ("Video call", ["Video call"]),
    ("Prescriptions (doctor and pharmacist)", ["Doctor and pharmacist"]),
    ("Community programmes: insurance, healers, lessons, training, fees", ["Community:"]),
    ("Facility management and equipment", ["Facility:"]),
    ("Pharmacist screens", ["Pharmacist"]),
    ("Ghana Health Service (GHS) officer dashboard", ["GHS officer"]),
    ("System administrator screens", ["System admin"]),
    ("SMS text messages", ["SMS to"]),
    ("Error messages shown to staff", ["Error shown"]),
]

# Short words that the app joins to a name, number or date on screen
HINTS = {
    "bookedFor": "followed by a date and time",
    "bookedBy": "followed by a person's name",
    "referredBy": "followed by a person's name",
    "referredOnTo": "followed by a hospital name",
    "callConnected": "followed by a person's name",
    "isCallingAbout": "[name] is calling about [patient number]",
    "savedCopy": "followed by a date and time",
    "pendingSync": "comes after a number, e.g. 2 check(s) saved...",
    "ghsThisWeek": "comes after a number, e.g. 12 cases this week",
    "ghsUsual": "followed by a number, e.g. usual ~4",
    "ghsWeeksAgo": "comes after a number, e.g. 3 weeks ago",
    "ghsUpdated": "followed by a date and time",
    "ghsForecastExpected": "followed by a number",
    "ghsForecastLevel": "e.g. outbreak level 10 a week",
    "ghsPerWeek": "e.g. 10 a week",
    "ghsForecastPrepare": "followed by an amount and a supply, e.g. Prepare: ~12 amoxicillin courses",
    "pwHint": "comes after the person's name, e.g. Ama Mensah: you are using...",
    "adminPasswordFor": "followed by a username",
    "adminResetConfirm": "followed by a username and ?",
    "checkFor": "followed by a list of illnesses",
    "inStock": "comes after a number, e.g. 150 in stock",
    "prescribedBy": "followed by a doctor's name",
    "dispensedBy": "followed by a pharmacist's name",
    "by": "followed by a person's name, e.g. Received by Ama",
    "healthFiring": "comes after a number, e.g. 2 alarm(s) need attention",
    "pharmaciesReporting": "followed by a number, e.g. Pharmacies: 2",
    "stockOutCount": "comes after a number of pharmacies, e.g. 1 out",
    "stockLowCount": "comes after a number of pharmacies, e.g. 2 low",
    "reorderAt": "followed by an amount, e.g. Reorder at 200 tablets",
    "quantity": "a box where the number is typed",
}

# The referral SMS is several labelled lines, so the translator gets each part separately
REFERRAL_SMS_PARTS = ["HealthConnect Referral", "Ref", "Age", "Visit", "Antenatal", "General",
                      "Risk", "Check for", "CHV", "Please prepare to receive this patient."]


def load_sections(new_only=False):
    """Group the CSV rows into SECTIONS, skipping strings no screen uses.
    new_only: just the lines with no translation in any language yet."""
    with CSV_FILE.open(encoding="utf-8-sig") as f:
        rows = [r for r in csv.DictReader(f) if not r["where it appears"].startswith("Not found")]
    if new_only:
        rows = [r for r in rows if r["key"] not in KEEP_ENGLISH and not any(r[lang] for lang in LANGUAGES)]
    grouped = {title: [] for title, _ in SECTIONS}
    for row in rows:
        first_screen = row["where it appears"].split(";")[0]
        title = next(t for t, starts in SECTIONS if any(first_screen.startswith(s) for s in starts))
        if row["key"] == "sms_referral":
            grouped[title] += [(f"sms_referral_{i}", part, "") for i, part in enumerate(REFERRAL_SMS_PARTS)]
        else:
            grouped[title].append((row["key"], row["English"], HINTS.get(row["key"], "")))
    return grouped


def main(new_only=False):
    pdf_file = NEW_PDF_FILE if new_only else PDF_FILE
    body = ParagraphStyle("body", fontName="Arial", fontSize=10, leading=13)
    hint = ParagraphStyle("hint", parent=body, fontSize=8, leading=10, textColor=colors.grey)
    head = ParagraphStyle("head", parent=body, fontName="Arial-Bold", fontSize=12, leading=15,
                          spaceBefore=14, spaceAfter=6)
    title = ParagraphStyle("title", parent=body, fontName="Arial-Bold", fontSize=17, leading=21)

    story = [
        Paragraph("HealthConnect Ghana: English text for translation", title),
        Spacer(1, 8),
        Paragraph(("These are the new lines added to HealthConnect since your last translation. "
                   if new_only else "This is every piece of English text in the HealthConnect app. ") + "Please write the "
                  "translation of each line in the empty column. Keep the number, so we can put each "
                  "translation in the right place.", body),
        Spacer(1, 4),
        Paragraph("• Keep translations short: most of them appear on buttons on small phone screens.<br/>"
                  "• Leave anything in {curly brackets} exactly as it is. The app fills it in "
                  "(for example {facility} becomes the clinic's name).<br/>"
                  "• Grey notes say what appears next to a word on screen. They do not need translating.<br/>"
                  "• Medical short forms such as BP, RDT, ORS and CHV can stay as they are.", body),
    ]

    number, numbers = 0, [("No.", "key", "English")]  # numbers: to map translations back to keys
    for section, items in load_sections(new_only).items():
        if not items:
            continue
        story.append(Paragraph(section, head))
        data = [[Paragraph("<b>No.</b>", body), Paragraph("<b>English</b>", body),
                 Paragraph("<b>Translation</b>", body)]]
        for key, english, note in items:
            number += 1
            numbers.append((number, key, english))
            cell = [Paragraph(escape(english), body)]
            if note:
                cell.append(Paragraph(escape(note), hint))
            data.append([Paragraph(str(number), body), cell, ""])
        table = Table(data, colWidths=[1.2 * cm, 8.4 * cm, 8.4 * cm], repeatRows=1)
        table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEF2F7")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 1), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 10),  # room to write by hand
        ]))
        story.append(table)

    def page_number(canvas, doc):
        canvas.setFont("Arial", 8)
        canvas.drawRightString(A4[0] - 1.5 * cm, 1 * cm, f"HealthConnect Ghana · page {doc.page}")

    doc = SimpleDocTemplate(str(pdf_file), pagesize=A4, leftMargin=1.5 * cm, rightMargin=1.5 * cm,
                            topMargin=1.5 * cm, bottomMargin=1.8 * cm,
                            title="HealthConnect Ghana: English text for translation")
    doc.build(story, onFirstPage=page_number, onLaterPages=page_number)
    numbers_file = HERE / ("pdf_numbers_new.csv" if new_only else "pdf_numbers.csv")
    with numbers_file.open("w", newline="", encoding="utf-8-sig") as f:
        csv.writer(f).writerows(numbers)
    print(f"Wrote {number} numbered lines to {pdf_file.name} (numbers in {numbers_file.name})")


if __name__ == "__main__":
    main(new_only="--new-only" in sys.argv)
