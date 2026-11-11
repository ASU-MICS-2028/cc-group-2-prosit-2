import { useState } from "react";
import { inputClass } from "./styles";

// field name, unit, example value (shown as placeholder)
const VITALS = [
  ["gestational_age", "weeks", "28"],
  ["systolic_bp", "mmHg", "120"],
  ["diastolic_bp", "mmHg", "80"],
  ["weight", "kg", "65"],
  ["hemoglobin", "g/dL", "11.5"],
  ["body_temp", "°C", "36.8"],
  ["heart_rate", "bpm", "80"],
  ["height", "cm", "160"],
];
const OPTIONAL = ["height"]; // not used in the risk score, so the check never waits for it

export default function AntenatalForm({ t, loading, onSubmit }) {
  const [vitals, setVitals] = useState({ previous_complications: false });

  const handleSubmit = (e) => {
    e.preventDefault();
    const body = { previous_complications: vitals.previous_complications };
    VITALS.forEach(([name]) => (body[name] = vitals[name] ? Number(vitals[name]) : null));
    onSubmit(body);
  };

  return (
    <form onSubmit={handleSubmit}>
      <div className="grid grid-cols-2 gap-3">
        {VITALS.map(([name, unit, example]) => (
          <div key={name}>
            <label className="mb-1 block text-xs font-medium text-stone-600">{t[name]}</label>
            <div className="relative">
              <input
                required={!OPTIONAL.includes(name)}
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
      <label className="mt-4 flex cursor-pointer items-center gap-3 text-sm text-stone-700">
        <input
          type="checkbox"
          checked={vitals.previous_complications}
          onChange={(e) => setVitals({ ...vitals, previous_complications: e.target.checked })}
          className="h-5 w-5 accent-teal-700"
        />
        {t.previous_complications}
      </label>
      <button
        type="submit"
        disabled={loading}
        className="mt-5 w-full rounded-xl bg-teal-700 py-3 font-semibold text-white hover:bg-teal-800 disabled:opacity-60"
      >
        {loading ? t.assessing : t.assess}
      </button>
    </form>
  );
}
