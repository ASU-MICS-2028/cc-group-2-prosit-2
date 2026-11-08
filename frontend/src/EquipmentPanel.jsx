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

  useEffect(() => {
    api("/equipment").then(setRows).catch(() => setRows([]));
  }, []);

  if (rows.length === 0) return <p className="mt-6 text-sm text-stone-500">{t.navEmpty}</p>;
  return (
    <div className="mt-6 rounded-2xl border border-stone-200 bg-white p-5 text-sm">
      <h2 className="text-lg font-semibold text-stone-800">{t.equipTitle}</h2>
      <div className="mt-2">
        <p className="mb-2 text-xs text-stone-500">{t.equipHint}</p>
        {rows.map((r) => <EquipmentRow key={r.item} t={t} row={r} onSaved={setRows} />)}
      </div>
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

  // Every device type reported anywhere becomes a column
  const devices = [...new Set(districts.flatMap((d) => d.items.map((i) => i.item)))];

  return (
    <div className="mt-6 rounded-2xl border border-stone-200 bg-white p-5">
      <h2 className="text-lg font-semibold text-stone-800">{t.equipDistrictTitle}</h2>
      <p className="text-xs text-stone-500">{t.equipDistrictHint}</p>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
      <div className="mt-3 overflow-x-auto">
        <table className="w-full text-sm" style={{ minWidth: 560 }}>
          <thead>
            <tr className="text-left text-xs text-stone-500">
              <th className="py-1 pr-3 font-medium">{t.impactDistrict}</th>
              {devices.map((item) => <th key={item} className="py-1 pr-3 font-medium">{t["equip_" + item]}</th>)}
            </tr>
          </thead>
          <tbody>
            {districts.map((d) => (
              <tr key={d.district} className="border-t border-stone-100">
                <td className="py-2 pr-3 font-medium text-stone-800">{d.district}</td>
                {devices.map((item) => {
                  const i = d.items.find((x) => x.item === item);
                  return (
                    <td key={item} className="py-2 pr-3 text-xs">
                      {i ? (
                        <span className="flex flex-wrap items-center gap-1">
                          <span className="tabular-nums text-stone-700">{i.working} {t.equipWorkingShort}</span>
                          {i.broken > 0 && <span className="rounded-full bg-amber-100 px-2 py-0.5 font-semibold text-amber-800">{i.broken} {t.equipBrokenShort}</span>}
                          {i.facilities_without > 0 && <span className="rounded-full bg-red-100 px-2 py-0.5 font-semibold text-red-700">{i.facilities_without} {t.equipWithout}</span>}
                        </span>
                      ) : "–"}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
