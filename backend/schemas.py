from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class PatientCreate(BaseModel):
    full_name: str
    age: int
    community: str = ""
    consent: bool


class PatientData(BaseModel):
    # Vitals for one antenatal check (age comes from the patient record)
    age: int
    gestational_age: int
    systolic_bp: int
    diastolic_bp: int
    weight: float
    hemoglobin: float
    body_temp: float
    heart_rate: int
    previous_complications: bool


class VitalsIn(BaseModel):
    gestational_age: int
    systolic_bp: int
    diastolic_bp: int
    weight: float
    hemoglobin: float
    body_temp: float
    heart_rate: int
    previous_complications: bool
    # Set by the phone when the check was done offline and synced later (UTC)
    recorded_at: datetime | None = None


class ReferralUpdate(BaseModel):
    status: Literal["arrived", "completed"]
    outcome: str | None = None
