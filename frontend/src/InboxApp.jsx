import { useState, useEffect } from "react";
import { api } from "./api";
import Header from "./Header";
import RiskBadge from "./RiskBadge";
import { VisitSummary } from "./PatientDetail";
import PatientHistory from "./PatientHistory";
import { AppointmentsPanel, BookAppointment } from "./AppointmentsPanel";
import { REFERRAL_STYLE, inputClass } from "./styles";

const PRIORITY_STYLE = {
  urgent: "bg-red-600 text-white",
  high: "bg-orange-100 text-orange-800",
  routine: "bg-stone-100 text-stone-600",
};

// 45 -> "45m", 130 -> "2h 10m", 1500 -> "1d 1h"
function formatWait(mins) {
  if (mins < 60) return `${mins}m`;
  if (mins < 1440) return `${Math.floor(mins / 60)}h ${mins % 60}m`;
  return `${Math.floor(mins / 1440)}d ${Math.floor((mins % 1440) / 60)}h`;
}

// Shared by nurses (health centre) and doctors (hospital): each sees only their own facility
export default function InboxApp(props) {
  const { t, user } = props;
  const isNurse = user.role === "nurse";
  const [referrals, setReferrals] = useState([]);
  const [hospitals, setHospitals] = useState([]); // where a nurse can refer onward
  const [apptKey, setApptKey] = useState(0); // bump to reload the appointments panel
  const [filter, setFilter] = useState("pending"); // all | pending | arrived | completed
  const [error, setError] = useState("");

  const load = () => api("/referrals").then(setReferrals).catch((err) => setError(err.message));

  useEffect(() => {
    api("/referrals").then(setReferrals).catch((err) => setError(err.message));
    if (isNurse) api("/facilities/hospitals").then(setHospitals).catch(() => {});
  }, [isNurse]);

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
        <h1 className="text-2xl font-bold text-stone-800">{isNurse ? t.inbox : t.doctorInbox}</h1>
        <p className="mt-1 text-sm text-stone-500">
          {isNurse ? t.inboxHint : t.doctorInboxHint} <span className="font-medium text-stone-700">{user.facility}</span>
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

        <AppointmentsPanel t={t} refreshKey={apptKey} />

        {error && <p className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

        <div className="mt-5 space-y-3">
          {shown.length === 0 && (
            <div className="rounded-2xl border border-dashed border-stone-300 bg-white p-10 text-center text-sm text-stone-500">
              {t.noReferrals}
            </div>
          )}
          {shown.map((r) => (
            <ReferralCard key={r.id} r={r} t={t} isNurse={isNurse} hospitals={hospitals} onChanged={load} onBooked={() => setApptKey((k) => k + 1)} />
          ))}
        </div>

        <p className="mt-12 text-center text-xs text-stone-400">{t.builtBy}</p>
      </main>
    </div>
  );
}

function ReferralCard({ r, t, isNurse, hospitals, onChanged, onBooked }) {
  const [mode, setMode] = useState(null); // null | "outcome" (doctor writing the outcome)
  const [showHistory, setShowHistory] = useState(false);
  const [outcome, setOutcome] = useState("");
  const [hospital, setHospital] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const send = async (path, body) => {
    setError("");
    setSaving(true);
    try {
      await api(path, { method: "POST", body });
      setMode(null);
      onChanged();
    } catch (err) {
      setError(err.message);
    }
    setSaving(false);
  };
  const update = (status) => send(`/referrals/${r.id}/status`, { status, outcome });
  // If there is only one hospital, choose it for the nurse
  const chosenHospital = hospital || (hospitals.length === 1 ? hospitals[0] : "");
  const escalate = () => send(`/referrals/${r.id}/escalate`, { facility: chosenHospital, reason });

  // Team rule: every patient must reach a doctor. Nurses refer on (once the patient
  // is physically here); only doctors record the final outcome.
  const canEscalate = isNurse && r.status === "arrived";
  const canComplete = !isNurse;

  return (
    <div
      className={`rounded-2xl border bg-white p-5 ${
        r.priority_label === "urgent" && r.status !== "completed" ? "border-red-300 ring-2 ring-red-100" : "border-stone-200"
      }`}
    >
      {/* Why this card is where it is in the list */}
      {r.status !== "completed" && (
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <span className={`rounded-full px-2.5 py-1 text-xs font-bold uppercase tracking-wide ${PRIORITY_STYLE[r.priority_label]}`}>
            {t["priority_" + r.priority_label]}
          </span>
          {r.danger_signs.map((d) => (
            <span key={d} className="rounded-full bg-red-50 px-2 py-0.5 text-xs font-medium text-red-700 ring-1 ring-red-200">
              ⚠ {t["sym_" + d] || t["ds_" + d] || d}
            </span>
          ))}
          <span className="ml-auto text-xs text-stone-500">
            {t.waiting} {formatWait(r.waiting_minutes)}
          </span>
        </div>
      )}
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

      {r.reason && (
        <p className="mt-3 rounded-xl bg-amber-50 px-3 py-2 text-sm text-amber-900">
          <span className="font-semibold">{t.reason}:</span> {r.reason}
        </p>
      )}

      <p className="mt-3 text-xs text-stone-500">
        {t.referredBy} {r.referred_by_name}
        {r.from_facility && ` (${r.from_facility})`}
        {r.parent_id && ` · ${t.chvLabel}: ${r.chv_name}`} · {r.created_at}
      </p>

      <button onClick={() => setShowHistory(!showHistory)} className="mt-3 text-sm font-medium text-teal-700 hover:underline">
        {showHistory ? `▾ ${t.hideHistory}` : `▸ ${t.viewHistory}`}
      </button>
      {showHistory && <PatientHistory referralId={r.id} t={t} />}
      <BookAppointment referralId={r.id} t={t} onBooked={onBooked} />

      {r.outcome && <p className="mt-3 rounded-xl bg-emerald-50 px-3 py-2 text-sm text-emerald-900">{r.outcome}</p>}

      {error && <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

      {r.status !== "completed" && !mode && (
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
          {canComplete && (
            <button
              onClick={() => setMode("outcome")}
              className="rounded-xl bg-teal-700 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-800"
            >
              {t.recordOutcome}
            </button>
          )}
        </div>
      )}
      {isNurse && r.status !== "completed" && !mode && <p className="mt-2 text-xs text-stone-500">{t.nurseMustRefer}</p>}

      {/* Nurse: treatment notes + referral to doctor, always visible once the patient has arrived */}
      {canEscalate && (
        <div className="mt-4 space-y-3 rounded-xl border border-violet-200 bg-violet-50/50 p-4">
          <div>
            <label className="mb-1 block text-sm font-semibold text-violet-900">{t.treatmentNotes}</label>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={3}
              maxLength={300}
              placeholder={t.escalateReasonPlaceholder}
              className={inputClass}
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-semibold text-violet-900">{t.sendTo}</label>
            <select value={chosenHospital} onChange={(e) => setHospital(e.target.value)} className={inputClass}>
              <option value="" disabled>
                {t.chooseHospital}
              </option>
              {hospitals.map((h) => (
                <option key={h} value={h}>
                  {h}
                </option>
              ))}
            </select>
          </div>
          <button
            onClick={escalate}
            disabled={saving || !chosenHospital || reason.trim().length < 3}
            className="rounded-xl bg-violet-700 px-4 py-2 text-sm font-semibold text-white hover:bg-violet-800 disabled:opacity-50"
          >
            {saving ? t.sending : t.escalate}
          </button>
        </div>
      )}

      {mode === "outcome" && (
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
            <button onClick={() => setMode(null)} className="rounded-xl px-4 py-2 text-sm text-stone-600 hover:bg-stone-100">
              {t.cancel}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
