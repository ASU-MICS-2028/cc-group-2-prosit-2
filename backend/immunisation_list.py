"""Ghana's childhood immunisation schedule (EPI: Expanded Programme on Immunisation).

Based on the GHS schedule as published; schedules change, so check it against the current
Maternal and Child Health Record Book before real use. Ages are in days after birth.
"""
# code, vaccine shown to the CHV, due at age (days), what it protects against
SCHEDULE = [
    ("bcg", "BCG", 0, "tuberculosis"),
    ("opv0", "OPV 0 (polio drops)", 0, "polio"),
    ("penta1", "Penta 1", 42, "diphtheria, tetanus, whooping cough, hepatitis B, Hib"),
    ("opv1", "OPV 1", 42, "polio"),
    ("pcv1", "PCV 1", 42, "pneumonia, meningitis"),
    ("rota1", "Rota 1", 42, "diarrhoea (rotavirus)"),
    ("penta2", "Penta 2", 70, "diphtheria, tetanus, whooping cough, hepatitis B, Hib"),
    ("opv2", "OPV 2", 70, "polio"),
    ("pcv2", "PCV 2", 70, "pneumonia, meningitis"),
    ("rota2", "Rota 2", 70, "diarrhoea (rotavirus)"),
    ("penta3", "Penta 3", 98, "diphtheria, tetanus, whooping cough, hepatitis B, Hib"),
    ("opv3", "OPV 3", 98, "polio"),
    ("pcv3", "PCV 3", 98, "pneumonia, meningitis"),
    ("ipv1", "IPV 1 (polio injection)", 98, "polio"),
    ("malaria1", "Malaria vaccine 1", 182, "malaria"),
    ("malaria2", "Malaria vaccine 2", 213, "malaria"),
    ("malaria3", "Malaria vaccine 3", 274, "malaria"),
    ("mr1", "Measles-Rubella 1", 274, "measles, rubella"),
    ("yf", "Yellow fever", 274, "yellow fever"),
    ("mr2", "Measles-Rubella 2", 548, "measles, rubella"),
    ("mena", "Meningitis A", 548, "meningitis A"),
    ("malaria4", "Malaria vaccine 4", 730, "malaria"),
]
CODES = {code for code, *_ in SCHEDULE}
GRACE_DAYS = 28  # a dose is "overdue" once it is 4 weeks late
DUE_SOON_DAYS = 14  # shown on the CHV's list two weeks ahead
MAX_AGE_YEARS = 5  # tracked for children under 5
