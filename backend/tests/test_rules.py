"""The risk rules, and proof that the browser copy (offline) gives the same answers."""
import itertools
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from general_model import assess_general
from model import predict_risk
from priority import priority
from schemas import PatientData

FRONTEND_SRC = Path(__file__).resolve().parents[2] / "frontend" / "src"


def antenatal(**changes):
    v = dict(age=25, gestational_age=30, systolic_bp=110, diastolic_bp=70, weight=60,
             hemoglobin=12, body_temp=36.8, heart_rate=80, previous_complications=False)
    v.update(changes)
    return predict_risk(PatientData(**v))


def test_antenatal_levels():
    assert antenatal() == (0.0, "LOW")
    assert antenatal(systolic_bp=140) == (0.4, "MEDIUM")  # hypertension alone
    assert antenatal(systolic_bp=140, hemoglobin=10) == (0.55, "HIGH")  # + mild anaemia
    assert antenatal(hemoglobin=6.9, previous_complications=True) == (0.5, "HIGH")  # boundary: 50 = HIGH


def test_general_levels_and_conditions():
    assert assess_general(None, None, None, None, []) == ("LOW", [])
    level, conditions = assess_general(38.5, None, None, None, ["fever"])
    assert level == "MEDIUM" and "malaria" in conditions
    level, conditions = assess_general(39, None, None, None, ["fever", "stiff_neck"])
    assert level == "HIGH" and "meningitis" in conditions  # stiff neck is a danger sign
    level, conditions = assess_general(None, None, None, None, ["diarrhoea", "vomiting"])
    assert level == "MEDIUM" and "cholera" in conditions


def referral(**changes):
    row = dict(risk_level="HIGH", status="pending", symptoms="", systolic_bp=None, diastolic_bp=None,
               hemoglobin=None, created_at="2026-01-01 08:00:00")
    row.update(changes)
    return row


def test_priority_score():
    from datetime import datetime, timezone
    now = datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc)  # 0 minutes waited
    assert priority(referral(), now)["priority_score"] == 50
    assert priority(referral(symptoms="convulsions"), now)["priority_label"] == "urgent"  # 50 + 30
    later = datetime(2026, 1, 2, 8, 0, tzinfo=timezone.utc)  # a day later: waiting points capped at 30
    assert priority(referral(risk_level="MEDIUM"), later)["priority_score"] == 20 + 30


# ---------- Same answers online and offline ----------

def run_js(code):
    if not shutil.which("node"):
        pytest.skip("Node.js not installed")
    out = subprocess.run(["node", "--input-type=module"], input=code, capture_output=True, text=True, check=True)  # stdin: no length limit
    return json.loads(out.stdout)


def test_antenatal_rules_match_browser_copy():
    grid = list(itertools.product([17, 18, 25, 35, 36], [27, 28], [129, 130, 139, 140], [79, 80, 89, 90],
                                  [6.9, 7, 10.9, 11], [False, True]))
    js = run_js(f"""
        import {{ predictRisk }} from "{FRONTEND_SRC / 'riskModel.js'}";
        const grid = {json.dumps(grid)};
        console.log(JSON.stringify(grid.map(([age, ga, sys, dia, hb, pc]) => {{
          const r = predictRisk(age, {{ gestational_age: ga, systolic_bp: sys, diastolic_bp: dia, hemoglobin: hb, previous_complications: pc }});
          return [r.risk_score, r.risk_level];
        }})));
    """)
    py = [list(antenatal(age=a, gestational_age=g, systolic_bp=s, diastolic_bp=d, hemoglobin=h, previous_complications=p))
          for a, g, s, d, h, p in grid]
    assert py == js, "model.py and riskModel.js disagree: change both together"


def test_general_rules_match_browser_copy():
    symptom_sets = [[], ["fever"], ["fever", "rash"], ["fever", "stiff_neck"], ["diarrhoea", "vomiting"],
                    ["cough", "fever", "difficulty_breathing"], ["cough", "rash", "vomiting"], ["bleeding"],
                    ["snake_bite"], ["chest_pain"], ["animal_bite"], ["other"], ["injury"], ["burn"], ["mental_distress"], ["abdominal_pain"]]
    grid = list(itertools.product([None, 34.9, 35, 38, 39.5], [None, 89, 90, 140, 160], [None, 90, 110],
                                  [None, 100, 101, 121], symptom_sets))
    js = run_js(f"""
        import {{ assessGeneral }} from "{FRONTEND_SRC / 'generalModel.js'}";
        const grid = {json.dumps(grid)};
        console.log(JSON.stringify(grid.map(([t, s, d, hr, sy]) => {{
          const r = assessGeneral({{ temperature: t, systolic_bp: s, diastolic_bp: d, heart_rate: hr, symptoms: sy }});
          return [r.risk_level, r.possible_conditions];
        }})));
    """)
    py = [list(assess_general(t, s, d, hr, sy)) for t, s, d, hr, sy in grid]
    assert py == js, "general_model.py and generalModel.js disagree: change both together"
