import { useState, useEffect } from "react";
import { api } from "./api";
import { inputClass } from "./styles";

function EquipmentRow({ t, row, onSaved }) {
  const [working, setWorking] = useState(String(row.working));
  const [broken, setBroken] = useState(String(row.broken));
  const [error, setError] = useState("");

  const save = async () => {
    setError("");
    try {
      onSaved(await api(`/equipment/${row.item}`, { method: "POST", body: { working: Number(working), broken: Number(broken) } }));
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="grid grid-cols-2 items-end gap-2 border-t border-stone-100 py-2 sm:grid-cols-4">
      <p className="col-span-2 font-medium text-stone-800 sm:col-span-1">{t["equip_" + row.item]}</p>
      <label className="text-xs text-stone-500">
        {t.equipWorking}
        <input type="number" min="0" value={working} onChange={(e) => setWorking(e.target.value)} className={inputClass} />
      </label>
      <label className="text-xs text-stone-500">
        {t.equipBroken}
        <input type="number" min="0" value={broken} onChange={(e) => setBroken(e.target.value)} className={inputClass} />
      </label>
      <button onClick={save} className="rounded-xl border border-stone-300 px-3 py-2 text-sm font-medium text-stone-700 hover:bg-stone-100">
        {t.saveChanges}
      </button>
      {error && <p className="col-span-2 text-sm text-red-600 sm:col-span-4">{error}</p>}
    </div>
  );
}

// Nurse / doctor: how many of each device this facility has, and how many are broken
export default function EquipmentPanel({ t }) {
  const [rows, setRows] = useState([]);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    api("/equipment").then(setRows).catch(() => setRows([]));
  }, []);

  if (rows.length === 0) return null;
  return (
    <div className="mt-6 rounded-2xl border border-stone-200 bg-white p-5 text-sm">
      <button onClick={() => setOpen(!open)} className="text-lg font-semibold text-stone-800">
        {open ? "▾" : "▸"} 🩺 {t.equipTitle}
      </button>
      {open && (
        <div className="mt-2">
          <p className="mb-2 text-xs text-stone-500">{t.equipHint}</p>
          {rows.map((r) => <EquipmentRow key={r.item} t={t} row={r} onSaved={setRows} />)}
        </div>
      )}
    </div>
  );
}

// GHS: equipment by district. Device counts only, no patient data.
export function EquipmentByDistrict({ t }) {
  const [districts, setDistricts] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    api("/surveillance/equipment")
      .then((data) => setDistricts(data.districts))
      .catch((err) => setError(err.message));
  }, []);

  return (
    <div className="mt-6 rounded-2xl border border-stone-200 bg-white p-5">
      <h2 className="text-lg font-semibold text-stone-800">🩺 {t.equipDistrictTitle}</h2>
      <p className="text-xs text-stone-500">{t.equipDistrictHint}</p>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        {districts.map((d) => (
          <div key={d.district} className="rounded-xl border border-stone-200 p-3">
            <p className="font-semibold text-stone-900">
              {d.district} <span className="text-xs font-normal text-stone-500">· {t.equipFacilities}: {d.facilities}</span>
            </p>
            <ul className="mt-2 space-y-1 text-sm">
              {d.items.map((i) => (
                <li key={i.item} className="flex items-start justify-between gap-2">
                  <span className="text-stone-700">{t["equip_" + i.item]}</span>
                  <span className="whitespace-nowrap text-xs tabular-nums">
                    {i.working} {t.equipWorkingShort}
                    {i.broken > 0 && <span className="ml-1 rounded-full bg-amber-100 px-2 py-0.5 font-semibold text-amber-800">{i.broken} {t.equipBrokenShort}</span>}
                    {i.facilities_without > 0 && <span className="ml-1 rounded-full bg-red-100 px-2 py-0.5 font-semibold text-red-700">{i.facilities_without} {t.equipWithout}</span>}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}
