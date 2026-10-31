from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from schemas import PatientData
from model import predict_risk
import requests
import os
from dotenv import load_dotenv

load_dotenv()
# Only report whether the key exists; never print the secret itself
if not os.getenv("ARKESEL_API_KEY"):
    print("WARNING: ARKESEL_API_KEY is not set; /send-sms will fail")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/predict")
def predict(patient: PatientData):
    risk_score, risk_level = predict_risk(patient)
    
    # Temporary mock explanation (swap with Claude API once credits are added)
    explanation = f"This patient is {risk_level} risk due to the combination of blood pressure readings, hemoglobin levels, and obstetric history. The CHW should {'refer immediately to the nearest health facility' if risk_level == 'HIGH' else 'monitor closely and schedule a follow-up visit'}."

    return {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "explanation": explanation
    }

@app.get("/")
def root():
    return {"message": "SafeArrive API is running"}

@app.post("/send-sms")
def send_sms(data: dict):
    api_key = os.getenv("ARKESEL_API_KEY")
    
    # Format number to 233 format
    phone = data['facility_phone'].strip()
    if phone.startswith("0"):
        phone = "233" + phone[1:]
    
    message = f"""SafeArrive Alert 🚨
Ref: {data['patient_ref']}
Age: {data['age']}
Risk: {data['risk_level']}
CHW: {data['chw_name']}
Facility: {data['facility']}
Please prepare to receive this patient immediately."""

    response = requests.get(
        "https://sms.arkesel.com/sms/api",
        params={
            "action": "send-sms",
            "api_key": api_key,
            "to": phone,
            "from": "SafeArriv",
            "sms": message
        }
    )
    
    result = response.json()
    # Log only the status code; the full reply has account details we don't need
    print("ARKESEL STATUS:", result.get("code"))
    return {"success": result.get("code") == "ok"}