"""Triage rules for a general (non-antenatal) visit.

Prototype rules based on WHO danger signs; NOT clinically validated.
Mirrored in frontend/src/generalModel.js for offline use: change both together.
"""

SYMPTOMS = [
    "fever", "cough", "difficulty_breathing", "diarrhoea", "vomiting", "rash",
    "severe_headache", "stiff_neck", "convulsions", "unconscious", "bleeding", "unable_to_drink",
]

# Any one of these means the patient needs a facility now
DANGER_SIGNS = {"difficulty_breathing", "stiff_neck", "convulsions", "unconscious", "bleeding", "unable_to_drink"}


def assess_general(temperature, systolic_bp, diastolic_bp, heart_rate, symptoms):
    s = set(symptoms)
    t = temperature
    sys_bp = systolic_bp
    dia_bp = diastolic_bp
    hr = heart_rate

    high = (
        bool(s & DANGER_SIGNS)
        or (t is not None and (t >= 39.5 or t < 35))
        or (sys_bp is not None and (sys_bp >= 160 or sys_bp < 90))
        or (dia_bp is not None and dia_bp >= 110)
        or (hr is not None and hr > 120)
    )
    medium = (
        (t is not None and t >= 38)
        or {"diarrhoea", "vomiting"} <= s
        or (sys_bp is not None and sys_bp >= 140)
        or (dia_bp is not None and dia_bp >= 90)
        or (hr is not None and hr > 100)
        or len(s) >= 3
    )
    risk_level = "HIGH" if high else "MEDIUM" if medium else "LOW"
    return risk_level, possible_conditions(s, t, sys_bp, dia_bp)


def possible_conditions(s, t, sys_bp, dia_bp):
    # Symptom patterns to test or watch for. These feed the Week 3 outbreak dashboard.
    has_fever = "fever" in s or (t is not None and t >= 38)
    found = []
    if has_fever:
        found.append("malaria")  # Ghana guideline: test every fever (RDT)
    if has_fever and "stiff_neck" in s:
        found.append("meningitis")
    if has_fever and "rash" in s:
        found.append("measles")
    if "diarrhoea" in s and ("vomiting" in s or "unable_to_drink" in s):
        found.append("cholera")
    if "cough" in s and ("difficulty_breathing" in s or has_fever):
        found.append("pneumonia")
    if (sys_bp is not None and sys_bp >= 140) or (dia_bp is not None and dia_bp >= 90):
        found.append("hypertension")
    return found


def advice_for(risk_level):
    if risk_level == "HIGH":
        return "Danger signs: refer urgently to the nearest health facility."
    if risk_level == "MEDIUM":
        return "Test and treat per guidelines (e.g. malaria RDT), and review within 24 hours. Refer if not improving."
    return "Give home-care advice. Return if symptoms get worse."
