import { useState, useEffect } from "react";
import { api, apiBlobUrl } from "./api";
import { RX_STYLE, inputClass } from "./styles";

const EMPTY_ITEM = { drug_id: "", quantity: "", instructions: "" };

// The drugs in one prescription, e.g. "Amoxicillin ... × 15 tablets: 1 tablet 3 times a day"
export function RxItems({ rx, t, showStock = false }) {
  return (
    <ul className="mt-2 space-y-1 text-sm">
      {rx.items.map((i) => (
        <li key={i.drug_id} className="rounded-lg bg-stone-50 px-3 py-2">
          <span className="font-medium text-stone-800">{i.name}</span>{" "}
          {i.controlled && <span className="rounded-full bg-purple-100 px-2 py-0.5 text-xs font-semibold text-purple-800">🔒 {t.rxControlled}</span>}{" "}
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

// Code, expiry, and where it was dispensed: shown to doctors and pharmacists
export function RxCodeLine({ rx, t }) {
  if (!rx.code) return null;
  return (
    <p className="mt-2 text-xs text-stone-600">
      🔑 {t.rxCode} <span className="font-mono font-semibold text-stone-800">{rx.code}</span>
      {rx.valid_until && ` · ${t.rxValidUntil} ${rx.valid_until.slice(0, 10)}`}
      {rx.expired && <span className="ml-1 rounded-full bg-red-100 px-2 py-0.5 font-semibold text-red-700">{t.rxExpired}</span>}
      {rx.outside_pharmacy && (
        <span className="block text-teal-800">
          🏪 {t.rxDispensedAt} {rx.outside_pharmacy} ({t.rxLicence} {rx.outside_licence})
        </span>
      )}
    </p>
  );
}

// The slip the patient takes to ANY pharmacy: QR code + code. Printable.
export function RxSlip({ rx, t, onClose }) {
  const [qr, setQr] = useState(null);
  useEffect(() => {
    let url;
    apiBlobUrl(`/prescriptions/${rx.id}/qr.svg`)
      .then((u) => setQr((url = u)))
      .catch(() => {});
    return () => url && URL.revokeObjectURL(url);
  }, [rx.id]);
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-black/60 p-4">
      <div className="print-area w-full max-w-sm rounded-2xl bg-white p-5 text-stone-800">
        <p className="text-xs font-semibold uppercase tracking-wide text-teal-700">HealthConnect Ghana · {t.rxSlipTitle}</p>
        <p className="mt-1 text-lg font-semibold">{rx.full_name}</p>
        <p className="text-sm text-stone-500">
          <span className="font-mono">{rx.ref}</span> · {t.age} {rx.age}
        </p>
        <div className="mt-3 flex items-center gap-4">
          {qr ? <img src={qr} alt="" className="h-36 w-36" /> : <div className="h-36 w-36 animate-pulse rounded bg-stone-100" />}
          <div>
            <p className="text-xs text-stone-500">{t.rxCode}</p>
            <p className="font-mono text-2xl font-bold tracking-wider">{rx.code}</p>
            <p className="mt-1 text-xs text-stone-500">
              {t.rxValidUntil} {rx.valid_until?.slice(0, 10)}
            </p>
          </div>
        </div>
        <RxItems rx={rx} t={t} />
        <p className="mt-2 text-xs text-stone-500">
          {rx.prescribed_by_name} · {rx.facility} · {rx.created_at?.slice(0, 10)}
        </p>
        <p className="mt-2 rounded-lg bg-teal-50 px-3 py-2 text-xs text-teal-900">{t.rxSlipHint}</p>
        <div className="no-print mt-3 flex gap-2">
          <button onClick={() => window.print()} className="rounded-xl bg-teal-700 px-4 py-2 text-sm font-semibold text-white">
            🖨 {t.rxPrint}
          </button>
          <button onClick={onClose} className="rounded-xl px-4 py-2 text-sm text-stone-600 hover:bg-stone-100">
            {t.close}
          </button>
        </div>
      </div>
    </div>
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
  const [needReason, setNeedReason] = useState(false); // same drug prescribed recently: ask why
  const [duplicateReason, setDuplicateReason] = useState("");
  const [slip, setSlip] = useState(null);

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
      const body = {
        items: items.map((i) => ({ ...i, drug_id: Number(i.drug_id), quantity: Number(i.quantity) })),
        notes,
        duplicate_reason: duplicateReason,
      };
      await api(`/referrals/${referralId}/prescriptions`, { method: "POST", body });
      setOpen(false);
      setItems([EMPTY_ITEM]);
      setNotes("");
      setNeedReason(false);
      setDuplicateReason("");
      const list = await api(`/referrals/${referralId}/prescriptions`);
      setPrescriptions(list);
      setSlip(list[0]); // show the slip straight away: the patient needs the code
    } catch (err) {
      if (err.status === 409) setNeedReason(true);
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
          <RxCodeLine rx={rx} t={t} />
          <div className="mt-2 flex gap-4">
            {rx.status === "pending" && !rx.expired && (
              <button onClick={() => setSlip(rx)} className="text-xs font-semibold text-teal-700 hover:underline">
                🧾 {t.rxSlip}
              </button>
            )}
            {rx.status === "pending" && (
              <button onClick={() => cancel(rx.id)} className="text-xs font-medium text-red-700 hover:underline">
                {t.cancelPrescription}
              </button>
            )}
          </div>
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
          <p className="text-xs text-stone-500">{t.rxChecksHint}</p>
          {error && <p className="text-sm text-red-600">{error}</p>}
          {needReason && (
            <input value={duplicateReason} onChange={(e) => setDuplicateReason(e.target.value)} maxLength={200} placeholder={t.rxDuplicateReason} className={inputClass} />
          )}
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
      {slip && <RxSlip rx={slip} t={t} onClose={() => setSlip(null)} />}
    </div>
  );
}
