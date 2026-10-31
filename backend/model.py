from schemas import PatientData

def predict_risk(patient: PatientData):
    # Rule-based risk scoring (we'll replace with trained model later)
    score = 0

    if patient.systolic_bp >= 140 or patient.diastolic_bp >= 90:
        score += 40  # Hypertension - very high risk
    elif patient.systolic_bp >= 130 or patient.diastolic_bp >= 80:
        score += 20  # Elevated BP

    if patient.hemoglobin < 7:
        score += 30  # Severe anemia
    elif patient.hemoglobin < 11:
        score += 15  # Mild anemia

    if patient.age < 18 or patient.age > 35:
        score += 10  # Age risk

    if patient.previous_complications:
        score += 20  # Previous complications

    if patient.gestational_age < 28:
        score += 10  # Preterm risk

    # Determine risk level
    if score >= 50:
        risk_level = "HIGH"
    elif score >= 25:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    return round(score / 100, 2), risk_level