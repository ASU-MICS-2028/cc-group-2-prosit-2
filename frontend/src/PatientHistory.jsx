import { useState, useEffect } from "react";
import { api } from "./api";
import RiskBadge from "./RiskBadge";
import { VisitSummary } from "./PatientDetail";
import { REFERRAL_STYLE } from "./styles";

// All earlier visits of a referred patient, for the nurse or doctor handling the referral.
// Opened through the referral, so staff only ever see patients sent to their facility.
export default function PatientHistory({ referralId, t }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api(`/referrals/${referralId}/history`).then(setData).catch((err) => setError(err.message));
  }, [referralId]);

  if (error) return <p className="mt-3 text-sm text-red-600">{error}</p>;
  if (!data) return <p className="mt-3 text-sm text-stone-500">{t.loadingHistory}</p>;

  return (
    <div className="mt-3 rounded-xl border border-stone-200 bg-stone-50 p-4">
      <p className="text-sm font-semibold text-stone-800">
        {t.historyTitle} ({data.observations.length})
      </p>
      <p className="text-xs text-stone-500">
        {t.registered} {data.patient.created_at}
        {data.patient.pregnant ? ` · ${t.pregnantTag}` : ""}
      </p>

      {/* Timeline, newest first */}
      <ol className="mt-3 space-y-3 border-l-2 border-teal-200 pl-4">
        {data.observations.map((o) => (
          <li key={o.id} className="relative">
            <span className="absolute -left-[1.4rem] top-1.5 h-3 w-3 rounded-full border-2 border-white bg-teal-600" />
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-semibold text-stone-700">
                {o.visit_type === "general" ? t.generalVisit : t.antenatalCheck}
              </span>
              <span className="text-xs text-stone-500">{o.created_at}</span>
              <RiskBadge level={o.risk_level} t={t} />
            </div>
            <VisitSummary o={o} t={t} />
            {o.referral_status && (
              <p className="mt-1 text-xs text-stone-600">
                <span className={`rounded-full px-2 py-0.5 font-semibold ${REFERRAL_STYLE[o.referral_status]}`}>
                  {t["referral_" + o.referral_status]}
                </span>{" "}
                {o.referral_facility}
                {o.referral_outcome && ` · ${o.referral_outcome}`}
                {o.escalated_to && ` → ${o.escalated_to} (${t["referral_" + o.escalated_status]})`}
                {o.escalated_outcome && `: ${o.escalated_outcome}`}
              </p>
            )}
          </li>
        ))}
      </ol>
    </div>
  );
}
