import { useState, useEffect } from "react";
import { api } from "./api";
import Header from "./Header";
import RiskBadge from "./RiskBadge";
import { VisitSummary } from "./PatientDetail";
import { REFERRAL_STYLE, inputClass } from "./styles";

export default function NurseApp(props) {
  const { t, user } = props;
  const [referrals, setReferrals] = useState([]);
  const [filter, setFilter] = useState("pending"); // all | pending | arrived | completed
  const [error, setError] = useState("");

  const load = () => api("/referrals").then(setReferrals).catch((err) => setError(err.message));

  useEffect(() => {
    api("/referrals").then(setReferrals).catch((err) => setError(err.message));
  }, []);

  const count = (status) => referrals.filter((r) => r.status === status).length;
  const shown = filter === "all" ? referrals : referrals.filter((r) => r.status === filter);

  const tabs = [
    ["pending", t.pending, count("pending")],
    ["arrived", t.arrived, count("arrived")],
    ["completed", t.completed, count("completed")],
    ["all", t.all, referrals.length],
  ];

  return (
    <div className="min-h-screen bg-stone-50">
      <Header {...props} />
      <main className="mx-auto max-w-5xl px-4 py-6">
        <h1 className="text-2xl font-bold text-stone-800">{t.inbox}</h1>
        <p className="mt-1 text-sm text-stone-500">
          {t.inboxHint} <span className="font-medium text-stone-700">{user.facility}</span>
        </p>

        {/* Status tabs double as counters */}
        <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {tabs.map(([key, label, n]) => (
            <button
              key={key}
              onClick={() => setFilter(key)}
              className={`rounded-2xl border p-4 text-left transition ${
                filter === key ? "border-teal-600 bg-teal-50 ring-4 ring-teal-100" : "border-stone-200 bg-white hover:border-teal-300"
              }`}
            >
              <p className="text-xs font-medium text-stone-500">{label}</p>
              <p className="mt-1 text-3xl font-bold text-stone-800">{n}</p>
            </button>
          ))}
        </div>

        {error && <p className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

        <div className="mt-5 space-y-3">
          {shown.length === 0 && (
            <div className="rounded-2xl border border-dashed border-stone-300 bg-white p-10 text-center text-sm text-stone-500">
              {t.noReferrals}
            </div>
          )}
          {shown.map((r) => (
            <ReferralCard key={r.id} r={r} t={t} onChanged={load} />
          ))}
        </div>

        <p className="mt-12 text-center text-xs text-stone-400">{t.builtBy}</p>
      </main>
    </div>
  );
}

function ReferralCard({ r, t, onChanged }) {
  const [writing, setWriting] = useState(false);
  const [outcome, setOutcome] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const update = async (status) => {
    setError("");
    setSaving(true);
    try {
      await api(`/referrals/${r.id}/status`, { method: "POST", body: { status, outcome } });
      setWriting(false);
      onChanged();
    } catch (err) {
      setError(err.message);
    }
    setSaving(false);
  };

  return (
    <div className="rounded-2xl border border-stone-200 bg-white p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <p className="text-lg font-semibold text-stone-800">{r.full_name}</p>
            <RiskBadge level={r.risk_level} t={t} />
          </div>
          <p className="text-sm text-stone-500">
            <span className="font-mono">{r.ref}</span> · {t[r.sex] || ""} · {t.age} {r.age}
            {r.community && ` · ${r.community}`}
          </p>
          <p className="mt-1 text-xs font-semibold text-stone-600">
            {r.visit_type === "general" ? t.generalVisit : t.antenatalCheck}
          </p>
        </div>
        <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${REFERRAL_STYLE[r.status]}`}>
          {t["referral_" + r.status]}
        </span>
      </div>

      {/* The readings that triggered the referral */}
      {r.visit_type === "general" ? (
        <div className="mt-3 rounded-xl bg-stone-50 px-3 py-2">
          <VisitSummary o={r} t={t} />
        </div>
      ) : (
        <div className="mt-4 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
          {[
            ["BP", `${r.systolic_bp}/${r.diastolic_bp}`],
            ["Hb", `${r.hemoglobin} g/dL`],
            [t.gestational_age, `${r.gestational_age} wks`],
            [t.previousComplicationsShort, r.previous_complications ? "Yes" : "No"],
          ].map(([label, value]) => (
            <div key={label} className="rounded-xl bg-stone-50 px-3 py-2">
              <p className="text-xs text-stone-500">{label}</p>
              <p className="font-medium text-stone-800">{value}</p>
            </div>
          ))}
        </div>
      )}

      <p className="mt-3 text-xs text-stone-500">
        {t.referredBy} {r.chv_name} · {r.created_at}
      </p>

      {r.outcome && <p className="mt-3 rounded-xl bg-emerald-50 px-3 py-2 text-sm text-emerald-900">{r.outcome}</p>}

      {error && <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

      {r.status !== "completed" && !writing && (
        <div className="mt-4 flex flex-wrap gap-2">
          {r.status === "pending" && (
            <button
              onClick={() => update("arrived")}
              disabled={saving}
              className="rounded-xl bg-sky-600 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-700 disabled:opacity-60"
            >
              {t.markArrived}
            </button>
          )}
          <button
            onClick={() => setWriting(true)}
            className="rounded-xl bg-teal-700 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-800"
          >
            {t.recordOutcome}
          </button>
        </div>
      )}

      {writing && (
        <div className="mt-4 space-y-2">
          <textarea
            value={outcome}
            onChange={(e) => setOutcome(e.target.value)}
            rows={3}
            placeholder={t.outcomePlaceholder}
            className={inputClass}
          />
          <div className="flex gap-2">
            <button
              onClick={() => update("completed")}
              disabled={saving}
              className="rounded-xl bg-teal-700 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-800 disabled:opacity-60"
            >
              {t.saveOutcome}
            </button>
            <button onClick={() => setWriting(false)} className="rounded-xl px-4 py-2 text-sm text-stone-600 hover:bg-stone-100">
              {t.cancel}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
