import { useState } from "react";
import { inputClass } from "./styles";
import { SYMPTOMS, DANGER_SIGNS } from "./generalModel";

// field name, label key, unit, example
const VITALS = [
  ["temperature", "temperature", "°C", "37.0"],
  ["heart_rate", "heart_rate", "bpm", "80"],
  ["systolic_bp", "systolic_bp", "mmHg", "120"],
  ["diastolic_bp", "diastolic_bp", "mmHg", "80"],
];

export default function GeneralVisitForm({ t, loading, onSubmit }) {
  const [vitals, setVitals] = useState({});
  const [symptoms, setSymptoms] = useState([]);
  const [notes, setNotes] = useState("");
  const [error, setError] = useState("");

  const toggle = (code) =>
    setSymptoms(symptoms.includes(code) ? symptoms.filter((s) => s !== code) : [...symptoms, code]);

  const handleSubmit = (e) => {
    e.preventDefault();
    // Empty boxes are sent as null ("not measured"), not 0
    const body = { symptoms, notes };
    VITALS.forEach(([name]) => (body[name] = vitals[name] ? Number(vitals[name]) : null));
    if (symptoms.length === 0 && VITALS.every(([name]) => body[name] === null)) return setError(t.needSomething);
    setError("");
    onSubmit(body);
  };

  return (
    <form onSubmit={handleSubmit}>
      <p className="text-sm font-medium text-stone-700">{t.symptomsLabel}</p>
      <div className="mt-2 flex flex-wrap gap-2">
        {SYMPTOMS.map((code) => {
          const on = symptoms.includes(code);
          const danger = DANGER_SIGNS.includes(code);
          return (
            <button
              key={code}
              type="button"
              onClick={() => toggle(code)}
              className={`rounded-full border px-3 py-1.5 text-sm transition ${
                on
                  ? danger
                    ? "border-red-600 bg-red-600 text-white"
                    : "border-teal-700 bg-teal-700 text-white"
                  : "border-stone-300 bg-white text-stone-700 hover:border-teal-400"
              }`}
            >
              {on ? "✓ " : ""}
              {t["sym_" + code]}
              {danger && !on && <span className="ml-1 text-xs text-red-600">•</span>}
            </button>
          );
        })}
      </div>
      <p className="mt-2 text-xs text-stone-500">
        <span className="text-red-600">•</span> = {t.dangerSign}
      </p>

      <p className="mt-5 text-sm font-medium text-stone-700">{t.vitalsOptional}</p>
      <div className="mt-2 grid grid-cols-2 gap-3">
        {VITALS.map(([name, labelKey, unit, example]) => (
          <div key={name}>
            <label className="mb-1 block text-xs font-medium text-stone-600">{t[labelKey]}</label>
            <div className="relative">
              <input
                type="number"
                step="any"
                placeholder={example}
                value={vitals[name] ?? ""}
                onChange={(e) => setVitals({ ...vitals, [name]: e.target.value })}
                className={`${inputClass} pr-14`}
              />
              <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs text-stone-400">{unit}</span>
            </div>
          </div>
        ))}
      </div>

      <label className="mb-1 mt-5 block text-sm font-medium text-stone-700">{t.notes}</label>
      <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} maxLength={500} className={inputClass} />

      {error && <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

      <button
        type="submit"
        disabled={loading}
        className="mt-5 w-full rounded-xl bg-teal-700 py-3 font-semibold text-white hover:bg-teal-800 disabled:opacity-60"
      >
        {loading ? t.assessing : t.checkVisit}
      </button>
    </form>
  );
}
