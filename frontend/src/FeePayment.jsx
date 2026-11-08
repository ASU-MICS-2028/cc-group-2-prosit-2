import { useState, useEffect, useCallback } from "react";
import { api } from "./api";

// Pay a consultation or training fee through Paystack. Shows nothing when no fee is due.
export default function FeePayment({ t, kind, item, label, onPaid }) {
  const [fee, setFee] = useState(null);
  const [error, setError] = useState("");
  const path = `/fees/${kind}/${item}`;

  const load = useCallback(() => api(path).then(setFee).catch(() => setFee(null)), [path]);
  useEffect(() => { load(); }, [load]);

  const finish = (latest) => {
    setFee(latest);
    if (!latest.due && onPaid) onPaid();
  };
  const pay = async () => {
    setError("");
    try {
      finish(await api(path, { method: "POST" }));
    } catch (err) {
      setError(err.message);
    }
  };
  const confirm = async () => {
    setError("");
    try {
      await api(`/fees/confirm/${fee.pending.reference}`, { method: "POST" });
      finish(await api(path));
    } catch (err) {
      setError(err.message);
    }
  };

  if (!fee) return null;
  if (!fee.due) return <span className="text-xs font-semibold text-emerald-700">✓ {t.feePaid}</span>;
  const small = "rounded-lg border border-stone-300 px-2.5 py-1 text-xs font-medium text-stone-700 hover:bg-stone-100";
  return (
    <div className="flex flex-wrap items-center gap-2 text-xs">
      <span className="text-stone-600">{label}: GH₵{fee.amount_ghs}</span>
      {fee.live && <span className="font-semibold text-red-700">{t.feeLive}</span>}
      {fee.simulated && <span className="text-amber-700">{t.feeSimulated}</span>}
      <button onClick={pay} className={small}>{t.feePay}</button>
      {fee.pending && (
        <>
          <a href={fee.pending.checkout_url} target="_blank" rel="noreferrer" className="font-semibold text-teal-700 underline">{t.insOpenPaystack}</a>
          <button onClick={confirm} className={small}>{t.insCheckPaid}</button>
        </>
      )}
      {error && <span className="text-red-600">{error}</span>}
    </div>
  );
}
