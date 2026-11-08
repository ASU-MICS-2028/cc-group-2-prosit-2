import { useState, useEffect, useCallback } from "react";
import { api } from "./api";
import { inputClass } from "./styles";

// CHV, patient page: a traditional healer saw danger signs and sent this patient on.
// The CHV records it for the healer, who may not read or have a smartphone.
export default function HealerPanel({ t, patientId }) {
  const [healers, setHealers] = useState(null);
  const [referrals, setReferrals] = useState([]);
  const [open, setOpen] = useState(false);
  const [adding, setAdding] = useState(false);
  const [newHealer, setNewHealer] = useState({ full_name: "", community: "", registration_no: "" });
  const [form, setForm] = useState({ healer_id: "", signs: "", remedy_given: "" });
  const [error, setError] = useState("");

  const load = useCallback(() => {
    // No signal: leave the panel out rather than show an error on a page that otherwise works
    Promise.all([api("/healers"), api(`/patients/${patientId}/healer-referrals`)])
      .then(([h, r]) => {
        setHealers(h);
        setReferrals(r);
      })
      .catch(() => setHealers(null));
  }, [patientId]);
  useEffect(load, [load]);

  const addHealer = async () => {
    setError("");
    try {
      const healer = await api("/healers", { method: "POST", body: newHealer });
      setHealers([...healers, healer]);
      setForm({ ...form, healer_id: String(healer.id) });
      setNewHealer({ full_name: "", community: "", registration_no: "" });
      setAdding(false);
    } catch (err) {
      setError(err.message);
    }
  };

  const save = async () => {
    setError("");
    try {
      await api(`/patients/${patientId}/healer-referrals`, {
        method: "POST",
        body: { ...form, healer_id: Number(form.healer_id) },
      });
      setForm({ healer_id: "", signs: "", remedy_given: "" });
      setOpen(false);
      load();
    } catch (err) {
      setError(err.message);
    }
  };

  if (!healers) return null;
  const button = "rounded-xl bg-teal-700 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-800 disabled:opacity-50";
  const showAdd = adding || healers.length === 0;

  return (
    <div className="mt-3 rounded-xl border border-stone-200 p-3 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-semibold text-stone-800">🌿 {t.healerTitle}</p>
        {!open && (
          <button onClick={() => setOpen(true)} className="font-medium text-teal-700 hover:underline">
            {t.healerRecord}
          </button>
        )}
      </div>

      {referrals.map((r) => (
        <p key={r.id} className="mt-1 text-stone-600">
          {r.created_at.slice(0, 10)} · <span className="font-medium text-stone-800">{r.healer_name}</span>: {r.signs}
          {r.remedy_given && ` · ${t.healerRemedyShort}: ${r.remedy_given}`}
        </p>
      ))}

      {open && (
        <div className="mt-2 space-y-2 rounded-xl border border-teal-200 bg-teal-50/50 p-3">
          {showAdd ? (
            <div className="space-y-2">
              <p className="text-xs text-stone-500">{t.healerAddHint}</p>
              <input placeholder={t.healerName} value={newHealer.full_name} onChange={(e) => setNewHealer({ ...newHealer, full_name: e.target.value })} className={inputClass} />
              <input placeholder={t.healerCommunity} value={newHealer.community} onChange={(e) => setNewHealer({ ...newHealer, community: e.target.value })} className={inputClass} />
              <input placeholder={t.healerRegistration} value={newHealer.registration_no} onChange={(e) => setNewHealer({ ...newHealer, registration_no: e.target.value })} className={inputClass} />
              <button onClick={addHealer} disabled={newHealer.full_name.trim().length < 2} className={button}>{t.healerAdd}</button>
            </div>
          ) : (
            <>
              <select value={form.healer_id} onChange={(e) => setForm({ ...form, healer_id: e.target.value })} className={inputClass}>
                <option value="">{t.healerChoose}</option>
                {healers.map((h) => <option key={h.id} value={h.id}>{h.full_name}</option>)}
              </select>
              <button onClick={() => setAdding(true)} className="text-xs font-medium text-teal-700 hover:underline">+ {t.healerAdd}</button>
              <input placeholder={t.healerSigns} value={form.signs} onChange={(e) => setForm({ ...form, signs: e.target.value })} className={inputClass} />
              <input placeholder={t.healerRemedy} value={form.remedy_given} onChange={(e) => setForm({ ...form, remedy_given: e.target.value })} className={inputClass} />
              <div className="flex gap-2">
                <button onClick={save} disabled={!form.healer_id || form.signs.trim().length < 3} className={button}>{t.saveChanges}</button>
                <button onClick={() => setOpen(false)} className="rounded-xl px-4 py-2 text-sm text-stone-600 hover:bg-stone-100">{t.cancel}</button>
              </div>
            </>
          )}
          {error && <p className="text-sm text-red-600">{error}</p>}
        </div>
      )}
    </div>
  );
}
