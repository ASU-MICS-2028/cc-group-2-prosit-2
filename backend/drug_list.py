"""Starter drug list: common medicines and test kits from Ghana's Essential Medicines List.

Chosen to match what HealthConnect already flags, so stock links to the "possible conditions"
and the outbreak forecast's "supplies to prepare". The reorder levels are examples for a
demo, not GHS guidance: each pharmacy sets its own.

Each entry: (name, unit, default reorder level, condition it is mainly for or None)
"""

STARTER_DRUGS = [
    ("Artemether-lumefantrine 20/120 mg tablets (pack of 24)", "packs",     20,  "malaria"),
    ("Sulfadoxine-pyrimethamine 500/25 mg tablet (IPTp)",      "tablets",   60,  "malaria"),
    ("Malaria rapid diagnostic test (RDT)",                    "tests",     50,  "malaria"),
    ("Oral rehydration salts (ORS) sachet",                    "sachets",   100, "cholera"),
    ("Zinc 20 mg dispersible tablet",                          "tablets",   100, "cholera"),
    ("Cholera rapid diagnostic test",                          "tests",     10,  "cholera"),
    ("Amoxicillin 250 mg dispersible tablet",                  "tablets",   200, "pneumonia"),
    ("Ceftriaxone 1 g injection",                              "vials",     20,  "meningitis"),
    ("Vitamin A 200,000 IU capsule",                           "capsules",  50,  "measles"),
    ("Methyldopa 250 mg tablet",                               "tablets",   100, "hypertension"),
    ("Nifedipine 20 mg tablet",                                "tablets",   100, "hypertension"),
    ("Magnesium sulphate 50% injection (5 g in 10 ml)",        "ampoules",  20,  "hypertension"),
    ("Paracetamol 500 mg tablet",                              "tablets",   500, None),
    ("Ferrous sulphate + folic acid tablet",                   "tablets",   300, None),
    ("Oxytocin 10 IU injection",                               "ampoules",  20,  None),
]
