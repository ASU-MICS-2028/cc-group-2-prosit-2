import pickle
import numpy as np
from schemas import PatientData

# Load trained model and encoder
with open("model.pkl", "rb") as f:
    model = pickle.load(f)

with open("label_encoder.pkl", "rb") as f:
    le = pickle.load(f)

def predict_risk(patient: PatientData):
    features = np.array([[
        patient.age,
        patient.systolic_bp,
        patient.diastolic_bp,
        patient.body_temp,
        patient.heart_rate,
    ]])

    prediction = model.predict(features)[0]
    probabilities = model.predict_proba(features)[0]
    risk_level = le.inverse_transform([prediction])[0]

    # Normalize to HIGH/MEDIUM/LOW
    risk_map = {
        "high risk": "HIGH",
        "mid risk": "MEDIUM", 
        "low risk": "LOW"
    }

    risk_score = round(float(max(probabilities)), 2)
    return risk_score, risk_map[risk_level]