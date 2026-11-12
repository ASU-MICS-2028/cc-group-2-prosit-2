import { useState, useEffect, useCallback } from "react";
import { api } from "./api";
import { inputClass } from "./styles";

const NETWORKS = [
  ["mtn", "MTN MoMo"],
  ["telecel", "Telecel Cash"],
  ["at", "AT Money"],
];

// Nurse / doctor inbox: is this patient covered today? Only the date, no payment details.
export function CoverageBadge({ t, until }) {
  const covered = until && until >= new Date().toISOString().slice(0, 10);
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${covered ? "bg-emerald-100 text-emerald-800" : "bg-stone-100 text-stone-600"}`}>
      {covered ? `✓ ${t.insCovered} ${until}` : t.insNotCovered}
    </span>
  );
}

// CHV, patient page: join the community scheme and pay premiums through Paystack.
export default function InsurancePanel({ t, patientId }) {
  const [info, setInfo] = useState(null);
  const [consent, setConsent] = useState(false);
  const [months, setMonths] = useState(1);
  const [network, setNetwork] = useState("mtn");
  const [error, setError] = useState("");

  const load = useCallback(() => {
    // No signal: leave the panel out rather than show an error on a page that otherwise works
    api(`/patients/${patientId}/insurance`).then(setInfo).catch(() => setInfo(null));
  }, [patientId]);
  useEffect(load, [load]);

  const send = async (path, body) => {
    setError("");
    try {
      setInfo(await api(`/patients/${patientId}/insurance/${path}`, { method: "POST", body }));
    } catch (err) {
      setError(err.message);
    }
  };

  if (!info) return null;
  const button = "rounded-xl bg-teal-700 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-800 disabled:opacity-50";

  return (
    <div className="mt-3 rounded-xl border border-stone-200 p-3 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-semibold text-stone-800">🛡 {t.insTitle}</p>
        {info.member && <CoverageBadge t={t} until={info.paid_until} />}
      </div>
      <p className={`mt-1 rounded-lg px-2 py-1 text-xs ${info.live ? "bg-red-50 font-semibold text-red-700" : "bg-amber-50 text-amber-800"}`}>
        {info.live ? t.insPaystackLive : info.simulated ? t.insSimulated : t.insPaystackTest}
      </p>

      {!info.member && (
        <div className="mt-2 space-y-2">
          <p className="text-stone-600">{t.insExplain.replace("{amount}", info.monthly_premium_ghs)}</p>
          <label className="flex items-start gap-2 text-stone-700">
            <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} className="mt-1" />
            {t.insConsent}
          </label>
          <button onClick={() => send("join", { consent })} disabled={!consent} className={button}>
            {t.insJoin}
          </button>
        </div>
      )}

      {info.member && (
        <div className="mt-2 flex flex-wrap items-end gap-2">
          <label className="text-xs text-stone-500">
            {t.insMonths}
            <select value={months} onChange={(e) => setMonths(Number(e.target.value))} className={inputClass}>
              {[1, 3, 6, 12].map((m) => <option key={m} value={m}>{m}</option>)}
            </select>
          </label>
          <label className="text-xs text-stone-500">
            {t.insNetwork}
            <select value={network} onChange={(e) => setNetwork(e.target.value)} className={inputClass}>
              {NETWORKS.map(([code, name]) => <option key={code} value={code}>{name}</option>)}
            </select>
          </label>
          <button onClick={() => send("pay", { months, network })} className={button}>
            {info.simulated ? t.insPay : t.insPayReal} GH₵{months * info.monthly_premium_ghs}
          </button>
        </div>
      )}

      {info.pending && (
        <div className="mt-2 space-y-2 rounded-lg bg-teal-50 p-2">
          <p className="text-xs text-stone-700">{t.insPendingHint}</p>
          <div className="flex flex-wrap items-center gap-2">
            <a href={info.pending.checkout_url} target="_blank" rel="noreferrer" className={button}>{t.insOpenPaystack} GH₵{info.pending.amount_ghs}</a>
            <button onClick={() => send(`confirm/${info.pending.reference}`)} className="rounded-xl border border-stone-300 px-4 py-2 text-sm font-medium text-stone-700 hover:bg-stone-100">
              {t.insCheckPaid}
            </button>
          </div>
        </div>
      )}

      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}

      {info.payments.length > 0 && (
        <ul className="mt-2 space-y-0.5 text-xs text-stone-500">
          {info.payments.slice(0, 3).map((p) => (
            <li key={p.reference}>
              {p.created_at.slice(0, 10)} · GH₵{p.amount_ghs} · {p.months} {t.insMonthsShort} · <span className="font-mono">{p.reference}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
