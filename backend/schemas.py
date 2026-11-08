from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class AccountCreate(BaseModel):
    # Admin creates staff accounts. No password here: the server makes a temporary one.
    username: str = Field(pattern=r"^[a-z0-9_]{3,30}$")
    full_name: str = Field(min_length=1, max_length=100)
    role: Literal["chv", "nurse", "doctor", "pharmacist", "ghs", "admin"]
    facility: str = Field("", max_length=100)
    facility_phone: str = Field("", pattern=r"^$|^(0\d{9}|\+?233\d{9})$")  # where CHV referral SMS goes
    district: str = ""


class AccountActive(BaseModel):
    active: bool


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=72)  # bcrypt only reads the first 72 bytes


class PatientCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=100)
    age: int = Field(ge=0, le=120)
    sex: Literal["female", "male"]
    pregnant: bool = False
    # Optional, only for appointment reminders. Ghana format: 0XXXXXXXXX or 233XXXXXXXXX
    phone: str = Field("", pattern=r"^$|^(0\d{9}|\+?233\d{9})$")
    community: str = ""
    consent: bool


class PregnancyUpdate(BaseModel):
    pregnant: bool


Symptom = Literal[
    "fever", "cough", "difficulty_breathing", "diarrhoea", "vomiting", "rash",
    "severe_headache", "stiff_neck", "convulsions", "unconscious", "bleeding", "unable_to_drink",
]


class VisitIn(BaseModel):
    # General visit: every vital is optional (not every CHV has a BP cuff)
    temperature: float | None = Field(None, ge=30, le=45)
    systolic_bp: int | None = Field(None, ge=50, le=260)
    diastolic_bp: int | None = Field(None, ge=30, le=160)
    heart_rate: int | None = Field(None, ge=20, le=250)
    symptoms: list[Symptom] = []
    notes: str = Field("", max_length=500)
    recorded_at: datetime | None = None


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


class ReferralCreate(BaseModel):
    # Optional for HIGH risk; required for MEDIUM (the CHV's judgement must be explained)
    reason: str = Field("", max_length=300)


class EscalateIn(BaseModel):
    facility: str
    reason: str = Field(min_length=3, max_length=300)


class AppointmentCreate(BaseModel):
    scheduled_at: datetime  # Ghana time = UTC
    reason: str = Field("", max_length=200)


class AppointmentStatus(BaseModel):
    status: Literal["attended", "missed", "cancelled"]


class PrescriptionItem(BaseModel):
    drug_id: int
    quantity: int = Field(gt=0, le=10000)
    instructions: str = Field(min_length=3, max_length=200)  # e.g. "1 tablet 3 times a day for 5 days"


class PrescriptionCreate(BaseModel):
    items: list[PrescriptionItem] = Field(min_length=1, max_length=10)
    notes: str = Field("", max_length=300)


class StockReceive(BaseModel):
    quantity: int = Field(gt=0, le=100000)
    note: str = Field("", max_length=200)  # e.g. "Delivery from regional medical stores"


class StockAdjust(BaseModel):
    # After a count, or when stock expired or was damaged. The reason is required.
    new_quantity: int = Field(ge=0, le=100000)
    note: str = Field(min_length=3, max_length=200)


class ReorderLevel(BaseModel):
    reorder_level: int = Field(ge=0, le=100000)
