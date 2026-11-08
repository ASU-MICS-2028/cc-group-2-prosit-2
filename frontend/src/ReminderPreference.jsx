import { useState, useEffect } from "react";
import { api } from "./api";
import { LANGUAGES } from "./i18n";
import { inputClass } from "./styles";

// Many patients speak a Ghanaian language but cannot read it, so an SMS is not always right.
// sms = text message · chv = the CHV reminds the patient in person
const METHODS = ["sms", "chv"];

const languageName = (code) => LANGUAGES.find((l) => l.code === code)?.name || "";

// The two dropdowns, used when registering a patient and on the patient page
export function ReminderFields({ t, value, onChange }) {
  return (
    <div className="grid grid-cols-2 gap-3">
      <div>
        <label className="mb-1 block text-sm font-medium text-stone-700">{t.remindHow}</label>
        <select value={value.reminder_method} onChange={(e) => onChange({ ...value, reminder_method: e.target.value })} className={inputClass}>
          {METHODS.map((m) => (
            <option key={m} value={m}>
              {t["remind_" + m]}
            </option>
          ))}
        </select>
      </div>
      <div>
        <label className="mb-1 block text-sm font-medium text-stone-700">{t.speaksLanguage}</label>
        <select value={value.language || ""} onChange={(e) => onChange({ ...value, language: e.target.value })} className={inputClass}>
          <option value="">–</option>
          {LANGUAGES.map((l) => (
            <option key={l.code} value={l.code}>
              {l.name}
            </option>
          ))}
        </select>
      </div>
      <p className="col-span-2 -mt-1 text-xs text-stone-500">{t.remindHint}</p>
    </div>
  );
}

// Patient page: how this patient is reminded, with "Change"
export function ReminderSummary({ t, patient, onChanged }) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState({ reminder_method: patient.reminder_method || "sms", language: patient.language || "" });
  const [error, setError] = useState("");

  const save = async () => {
    try {
      await api(`/patients/${patient.id}/reminder-preference`, {
        method: "POST",
        body: { reminder_method: value.reminder_method, language: value.language || null },
      });
      setEditing(false);
      onChanged();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="mt-2 text-sm text-stone-600">
      {!editing ? (
        <p>
          🔔 {t.remindHow}: <span className="font-medium text-stone-800">{t["remind_" + (patient.reminder_method || "sms")]}</span>
          {patient.language && ` · ${languageName(patient.language)}`}{" "}
          <button onClick={() => setEditing(true)} className="font-medium text-teal-700 hover:underline">
            {t.change}
          </button>
        </p>
      ) : (
        <div className="space-y-2 rounded-xl border border-teal-200 bg-teal-50/50 p-3">
          <ReminderFields t={t} value={value} onChange={setValue} />
          {error && <p className="text-sm text-red-600">{error}</p>}
          <div className="flex gap-2">
            <button onClick={save} className="rounded-xl bg-teal-700 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-800">
              {t.saveChanges}
            </button>
            <button onClick={() => setEditing(false)} className="rounded-xl px-4 py-2 text-sm text-stone-600 hover:bg-stone-100">
              {t.cancel}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// CHV home: appointments in the next 7 days that an SMS will not reach, so the CHV visits
export function RemindInPersonList({ t, onOpen }) {
  const [items, setItems] = useState([]);

  useEffect(() => {
    api("/chv/reminders").then(setItems).catch(() => {}); // no signal: simply not shown
  }, []);

  if (items.length === 0) return null;
  return (
    <div className="mt-5 rounded-2xl border border-amber-200 bg-amber-50 p-4">
      <h2 className="font-semibold text-amber-900">🚶 {t.remindInPerson} ({items.length})</h2>
      <p className="text-xs text-amber-800">{t.remindInPersonHint}</p>
      <ul className="mt-2 divide-y divide-amber-200">
        {items.map((a) => (
          <li key={a.id}>
            <button onClick={() => onOpen(a.patient_id)} className="w-full py-2 text-left text-sm hover:underline">
              <span className="font-medium text-stone-800">{a.full_name}</span>{" "}
              <span className="font-mono text-xs text-stone-500">{a.ref}</span>
              {a.community && <span className="text-stone-600"> · {a.community}</span>}
              <span className="block text-xs text-stone-600">
                📅 {a.scheduled_at} · {a.facility}
                {a.language && ` · ${t.speaksShort} ${languageName(a.language)}`} · {t["remindWhy_" + (a.reminder_method !== "sms" ? a.reminder_method : a.reminder_status === "failed" ? "failed" : "no_phone")]}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
