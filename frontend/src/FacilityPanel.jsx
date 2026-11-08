import { useState, useEffect, useCallback } from "react";
import { api } from "./api";
import { inputClass } from "./styles";

// Health centre manager: run your own centre. Other staff never see this (the server says 403).
export default function FacilityPanel({ t }) {
  const [data, setData] = useState(null);
  const [fee, setFee] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(() => {
    api("/facility/overview").then((d) => { setData(d); setFee(String(d.consultation_fee_ghs)); }).catch(() => setData(null));
  }, []);
  useEffect(load, [load]);

  const send = async (path, body) => {
    setError("");
    try {
      await api(path, { method: "POST", body });
      load();
    } catch (err) {
      setError(err.message);
    }
  };

  if (!data) return null;
  const figures = ["visits", "referrals", "appointments", "consultation_fees_ghs", "premiums_ghs"];

  return (
    <div className="mt-6 rounded-2xl border border-stone-200 bg-white p-5 text-sm">
      <h2 className="text-lg font-semibold text-stone-800">🏘 {t.facilityTitle}: {data.facility}</h2>
      <p className="mt-1 text-xs text-stone-500">{t.facilityHint}</p>
      <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-5">
        {figures.map((f) => (
          <div key={f} className="rounded-xl bg-stone-50 p-3">
            <p className="text-xl font-bold tabular-nums text-stone-900">{data.this_month[f]}</p>
            <p className="text-xs text-stone-500">{t["facility_" + f]}</p>
          </div>
        ))}
      </div>
      <div className="mt-3 flex flex-wrap items-end gap-2">
        <label className="text-xs text-stone-500">
          {t.facilityFee} (GH₵)
          <input type="number" min="0" max="100" value={fee} onChange={(e) => setFee(e.target.value)} className={`${inputClass} max-w-[8rem]`} />
        </label>
        <button onClick={() => send("/facility/fee", { consultation_fee_ghs: Number(fee) })} className="rounded-xl bg-teal-700 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-800">{t.saveChanges}</button>
      </div>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
      <p className="mt-4 font-semibold text-stone-800">{t.facilityStaff}</p>
      <div className="mt-1 divide-y divide-stone-100">
        {data.staff.map((s) => (
          <div key={s.id} className="flex items-center justify-between gap-2 py-2">
            <span className={s.active ? "text-stone-800" : "text-stone-400"}>{s.full_name} <span className="text-xs text-stone-500">{t["role_" + s.role]}</span></span>
            {s.is_you ? <span className="text-xs text-stone-500">{t.adminYou}</span> : (
              <button onClick={() => send(`/facility/staff/${s.id}/active`, { active: !s.active })} className="rounded-full bg-stone-100 px-3 py-1 text-xs font-semibold text-stone-700 hover:bg-stone-200">
                {s.active ? t.adminDisable : t.adminEnable}
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
