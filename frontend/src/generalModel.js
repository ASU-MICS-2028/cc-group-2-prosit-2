// Same rules as backend/general_model.py, so general visits work offline.
// If you change a rule here, change it there too (the server re-checks on sync).

export const SYMPTOMS = [
  "fever", "cough", "difficulty_breathing", "diarrhoea", "vomiting", "rash",
  "severe_headache", "stiff_neck", "convulsions", "unconscious", "bleeding", "unable_to_drink",
  "chest_pain", "snake_bite", "animal_bite", "injury", "burn", "abdominal_pain", "mental_distress", "other",
];

// Any one of these means the patient needs a facility now
export const DANGER_SIGNS = ["difficulty_breathing", "stiff_neck", "convulsions", "unconscious", "bleeding", "unable_to_drink", "chest_pain", "snake_bite", "animal_bite"];

// Never just "home care": someone should look at these within 24 hours
const NEEDS_REVIEW = ["injury", "burn", "mental_distress", "other"];

const has = (v) => v !== null && v !== undefined;

export function assessGeneral({ temperature: t, systolic_bp: sys, diastolic_bp: dia, heart_rate: hr, symptoms }) {
  const s = new Set(symptoms);

  const high =
    DANGER_SIGNS.some((d) => s.has(d)) ||
    (has(t) && (t >= 39.5 || t < 35)) ||
    (has(sys) && (sys >= 160 || sys < 90)) ||
    (has(dia) && dia >= 110) ||
    (has(hr) && hr > 120);
  const medium =
    (has(t) && t >= 38) ||
    (s.has("diarrhoea") && s.has("vomiting")) ||
    (has(sys) && sys >= 140) ||
    (has(dia) && dia >= 90) ||
    (has(hr) && hr > 100) ||
    s.size >= 3 ||
    NEEDS_REVIEW.some((c) => s.has(c));

  const risk_level = high ? "HIGH" : medium ? "MEDIUM" : "LOW";
  return { risk_level, possible_conditions: possibleConditions(s, t, sys, dia), advice: generalAdvice(risk_level) };
}

function possibleConditions(s, t, sys, dia) {
  const hasFever = s.has("fever") || (has(t) && t >= 38);
  const found = [];
  if (hasFever) found.push("malaria"); // Ghana guideline: test every fever (RDT)
  if (hasFever && s.has("stiff_neck")) found.push("meningitis");
  if (hasFever && s.has("rash")) found.push("measles");
  if (s.has("diarrhoea") && (s.has("vomiting") || s.has("unable_to_drink"))) found.push("cholera");
  if (s.has("cough") && (s.has("difficulty_breathing") || hasFever)) found.push("pneumonia");
  if ((has(sys) && sys >= 140) || (has(dia) && dia >= 90)) found.push("hypertension");
  return found;
}

export function generalAdvice(level) {
  if (level === "HIGH") return "Danger signs: refer urgently to the nearest health facility.";
  if (level === "MEDIUM") return "Test and treat per guidelines (e.g. malaria RDT), and review within 24 hours. Refer if not improving.";
  return "Give home-care advice. Return if symptoms get worse.";
}
