from pydantic import BaseModel

class PatientData(BaseModel):
    age: int
    gestational_age: int
    systolic_bp: int
    diastolic_bp: int
    weight: float
    hemoglobin: float
    body_temp: float
    heart_rate: int
    previous_complications: bool