import { useState, useEffect } from "react";
import { api } from "./api";
import { RX_STYLE, inputClass } from "./styles";

const EMPTY_ITEM = { drug_id: "", quantity: "", instructions: "" };

// The drugs in one prescription, e.g. "Amoxicillin ... × 15 tablets: 1 tablet 3 times a day"
export function RxItems({ rx, t, showStock = false }) {
  return (
    <ul className="mt-2 space-y-1 text-sm">
      {rx.items.map((i) => (
        <li key={i.drug_id} className="rounded-lg bg-stone-50 px-3 py-2">
          <span className="font-medium text-stone-800">{i.name}</span>{" "}
          <span className="text-stone-600">
            × {i.quantity} {i.unit}
          </span>
          <span className="block text-xs text-stone-500">{i.instructions}</span>
          {/* Shortage warning before the pharmacist even tries to dispense */}
          {showStock && rx.status === "pending" && i.in_stock < i.quantity && (
            <span className="block text-xs font-semibold text-red-700">
              ⚠ {t.notEnoughHere} ({i.in_stock} {t.inStock})
            </span>
          )}
        </li>
      ))}
    </ul>
  );
}

// Doctor, on a referral card: earlier prescriptions + "Prescribe drugs" form
export function PrescribePanel({ referralId, t }) {
  const [prescriptions, setPrescriptions] = useState([]);
  const [drugs, setDrugs] = useState([]);
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState([EMPTY_ITEM]);
  const [notes, setNotes] = useState("");
  const [error, setError] = useState("");

  const load = () => api(`/referrals/${referralId}/prescriptions`).then(setPrescriptions).catch((err) => setError(err.message));

  useEffect(() => {
    api(`/referrals/${referralId}/prescriptions`).then(setPrescriptions).catch((err) => setError(err.message));
  }, [referralId]);

  const start = () => {
    setOpen(true);
    api("/drugs").then(setDrugs).catch((err) => setError(err.message));
  };

  const setItem = (index, field, value) => setItems(items.map((it, i) => (i === index ? { ...it, [field]: value } : it)));

  const send = async () => {
    setError("");
    try {
      const body = { items: items.map((i) => ({ ...i, drug_id: Number(i.drug_id), quantity: Number(i.quantity) })), notes };
      await api(`/referrals/${referralId}/prescriptions`, { method: "POST", body });
      setOpen(false);
      setItems([EMPTY_ITEM]);
      setNotes("");
      load();
    } catch (err) {
      setError(err.message);
    }
  };

  const cancel = async (id) => {
    try {
      await api(`/prescriptions/${id}/cancel`, { method: "POST" });
      load();
    } catch (err) {
      setError(err.message);
    }
  };

  const complete = items.every((i) => i.drug_id && Number(i.quantity) > 0 && i.instructions.trim().length >= 3);

  return (
    <div className="mt-3">
      {prescriptions.map((rx) => (
        <div key={rx.id} className="mb-2 rounded-xl border border-stone-200 p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm font-semibold text-stone-700">💊 {t.prescriptions} · {rx.created_at}</p>
            <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${RX_STYLE[rx.status]}`}>{t["rx_" + rx.status]}</span>
          </div>
          <RxItems rx={rx} t={t} />
          {rx.status === "pending" && (
            <button onClick={() => cancel(rx.id)} className="mt-2 text-xs font-medium text-red-700 hover:underline">
              {t.cancelPrescription}
            </button>
          )}
        </div>
      ))}

      {!open ? (
        <button onClick={start} className="text-sm font-medium text-teal-700 hover:underline">
          💊 {t.prescribe}
        </button>
      ) : (
        <div className="space-y-2 rounded-xl border border-teal-200 bg-teal-50/50 p-3">
          {items.map((item, index) => (
            <div key={index} className="space-y-2 rounded-lg bg-white p-2">
              <select value={item.drug_id} onChange={(e) => setItem(index, "drug_id", e.target.value)} className={inputClass}>
                <option value="">{t.chooseDrug}</option>
                {drugs.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name} ({d.in_stock} {t.inStock})
                  </option>
                ))}
              </select>
              <div className="flex gap-2">
                <input
                  type="number"
                  min="1"
                  value={item.quantity}
                  onChange={(e) => setItem(index, "quantity", e.target.value)}
                  placeholder={t.quantity}
                  className={`${inputClass} w-28`}
                />
                <input
                  value={item.instructions}
                  onChange={(e) => setItem(index, "instructions", e.target.value)}
                  maxLength={200}
                  placeholder={t.instructionsPlaceholder}
                  className={inputClass}
                />
              </div>
              {items.length > 1 && (
                <button onClick={() => setItems(items.filter((_, i) => i !== index))} className="text-xs text-red-700 hover:underline">
                  ✕ {t.removeDrug}
                </button>
              )}
            </div>
          ))}
          {items.length < 10 && (
            <button onClick={() => setItems([...items, EMPTY_ITEM])} className="text-sm font-medium text-teal-700 hover:underline">
              + {t.addDrug}
            </button>
          )}
          <input value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={300} placeholder={t.rxNotesPlaceholder} className={inputClass} />
          {error && <p className="text-sm text-red-600">{error}</p>}
          <div className="flex gap-2">
            <button
              onClick={send}
              disabled={!complete}
              className="rounded-xl bg-teal-700 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-800 disabled:opacity-50"
            >
              {t.sendToPharmacy}
            </button>
            <button onClick={() => setOpen(false)} className="rounded-xl px-4 py-2 text-sm text-stone-600 hover:bg-stone-100">
              {t.cancel}
            </button>
          </div>
        </div>
      )}
      {!open && error && <p className="mt-1 text-sm text-red-600">{error}</p>}
    </div>
  );
}
