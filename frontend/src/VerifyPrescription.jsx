import { useState, useEffect } from "react";
import { api } from "./api";
import { inputClass } from "./styles";
import Logo from "./Logo";

const STATUS_STYLE = {
  valid: "bg-emerald-100 text-emerald-800",
  dispensed: "bg-stone-200 text-stone-700",
  cancelled: "bg-red-100 text-red-700",
  expired: "bg-red-100 text-red-700",
};

// Public page for ANY pharmacy (no account): check a HealthConnect prescription and dispense it once.
// Opened by scanning the QR code on the slip (?rx=CODE) or by typing the code.
export default function VerifyPrescription({ t, initialCode, onBack }) {
  const [code, setCode] = useState(initialCode || "");
  const [rx, setRx] = useState(null);
  const [error, setError] = useState("");
  const [form, setForm] = useState({ pharmacy: "", licence: "", pharmacist: "", checked_patient: false });
  const [done, setDone] = useState(false);

  const check = async (value = code) => {
    setError("");
    setRx(null);
    setDone(false);
    try {
      setRx(await api(`/rx/${encodeURIComponent(value.trim())}`));
    } catch (err) {
      setError(err.message);
    }
  };
  // Opened from a QR code: check it straight away
  useEffect(() => {
    if (!initialCode) return;
    api(`/rx/${encodeURIComponent(initialCode.trim())}`)
      .then(setRx)
      .catch((err) => setError(err.message));
  }, [initialCode]);

  const dispense = async (e) => {
    e.preventDefault();
    setError("");
    try {
      await api(`/rx/${encodeURIComponent(rx.code)}/dispense`, { method: "POST", body: form });
      setDone(true);
      check(rx.code);
    } catch (err) {
      setError(err.message);
    }
  };
  const field = (name, label) => (
    <div>
      <label className="mb-1 block text-xs font-medium text-stone-600">{label}</label>
      <input value={form[name]} onChange={(e) => setForm({ ...form, [name]: e.target.value })} className={inputClass} required minLength={3} />
    </div>
  );

  return (
    <div className="min-h-screen bg-stone-50 px-4 py-6">
      <div className="mx-auto max-w-md">
        <div className="flex items-center justify-between">
          <Logo />
          <button onClick={onBack} className="text-sm text-teal-700 hover:underline">
            {t.rxBackToSignIn}
          </button>
        </div>
        <h1 className="mt-4 text-xl font-semibold text-stone-800">💊 {t.rxVerifyTitle}</h1>
        <p className="text-sm text-stone-500">{t.rxVerifyHint}</p>

        <form onSubmit={(e) => { e.preventDefault(); check(); }} className="mt-4 flex gap-2">
          <input value={code} onChange={(e) => setCode(e.target.value)} placeholder="7KQ4-M9TX" className={`${inputClass} font-mono uppercase`} />
          <button className="rounded-xl bg-teal-700 px-4 text-sm font-semibold text-white">{t.rxCheck}</button>
        </form>
        {error && <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

        {rx && (
          <div className="mt-4 rounded-2xl border border-stone-200 bg-white p-4">
            <div className="flex items-center justify-between">
              <span className="font-mono text-lg font-bold">{rx.code}</span>
              <span className={`rounded-full px-3 py-1 text-sm font-semibold ${STATUS_STYLE[rx.status]}`}>{t["rxStatus_" + rx.status]}</span>
            </div>
            <p className="mt-2 text-sm text-stone-700">
              {t.rxPatient}: <b>{rx.patient.initials}</b> · {t[rx.patient.sex] || rx.patient.sex} · {t.age} {rx.patient.age} ·{" "}
              <span className="font-mono text-xs">{rx.patient.ref}</span>
            </p>
            <ul className="mt-2 space-y-1 text-sm">
              {rx.items.map((i) => (
                <li key={i.name} className="rounded-lg bg-stone-50 px-3 py-2">
                  <span className="font-medium">{i.name}</span> × {i.quantity} {i.unit}
                  {i.controlled && <span className="ml-1 rounded-full bg-purple-100 px-2 py-0.5 text-xs font-semibold text-purple-800">🔒 {t.rxControlled}</span>}
                  <span className="block text-xs text-stone-500">{i.instructions}</span>
                </li>
              ))}
            </ul>
            <p className="mt-2 text-xs text-stone-500">
              {rx.prescribed_by} · {rx.facility} · {rx.created_at.slice(0, 10)} · {t.rxValidUntil} {rx.valid_until?.slice(0, 10)}
            </p>
            {rx.status === "dispensed" && (
              <p className="mt-2 rounded-lg bg-stone-100 px-3 py-2 text-sm text-stone-700">
                {done ? "✅ " : "⛔ "}
                {t.rxAlreadyDispensed} {rx.dispensed_where} · {rx.dispensed_at}
              </p>
            )}

            {rx.status === "valid" && (
              <form onSubmit={dispense} className="mt-4 space-y-3 border-t border-stone-100 pt-3">
                <p className="text-sm font-semibold text-stone-800">{t.rxRecordDispense}</p>
                {field("pharmacy", t.rxPharmacyName)}
                {field("licence", t.rxLicenceNumber)}
                {field("pharmacist", t.rxPharmacistName)}
                <label className="flex items-start gap-2 text-sm text-stone-700">
                  <input type="checkbox" checked={form.checked_patient} onChange={(e) => setForm({ ...form, checked_patient: e.target.checked })} className="mt-1" />
                  <span>{t.rxCheckedPatient}</span>
                </label>
                <button disabled={!form.checked_patient} className="w-full rounded-xl bg-teal-700 py-2.5 text-sm font-semibold text-white disabled:opacity-50">
                  {t.rxDispenseOnce}
                </button>
              </form>
            )}
          </div>
        )}
        <p className="mt-4 text-xs text-stone-400">{t.rxVerifyPrivacy}</p>
      </div>
    </div>
  );
}
