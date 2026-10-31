// Same rules as backend/model.py, so a CHV gets a result with no signal.
// If you change a rule here, change it in model.py too (the server re-scores on sync).
export function predictRisk(age, v) {
  let score = 0;

  if (v.systolic_bp >= 140 || v.diastolic_bp >= 90) score += 40; // Hypertension
  else if (v.systolic_bp >= 130 || v.diastolic_bp >= 80) score += 20; // Elevated BP

  if (v.hemoglobin < 7) score += 30; // Severe anaemia
  else if (v.hemoglobin < 11) score += 15; // Mild anaemia

  if (age < 18 || age > 35) score += 10; // Age risk
  if (v.previous_complications) score += 20; // Previous complications
  if (v.gestational_age < 28) score += 10; // Preterm risk

  const risk_level = score >= 50 ? "HIGH" : score >= 25 ? "MEDIUM" : "LOW";
  return { risk_score: Math.round(score) / 100, risk_level, advice: adviceFor(risk_level) };
}

export function adviceFor(level) {
  if (level === "HIGH") return "Refer immediately to the nearest health facility.";
  if (level === "MEDIUM") return "Monitor closely and schedule a follow-up visit.";
  return "Continue routine antenatal care.";
}
