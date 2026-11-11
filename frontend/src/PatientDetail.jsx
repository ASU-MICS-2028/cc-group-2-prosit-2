import { useState, useEffect, useRef, useCallback } from "react";
import { api } from "./api";
import RiskBadge from "./RiskBadge";
import ConditionChips from "./ConditionChips";
import AntenatalForm from "./AntenatalForm";
import GeneralVisitForm from "./GeneralVisitForm";
import { RISK_STYLE, REFERRAL_STYLE, inputClass } from "./styles";
import { predictRisk } from "./riskModel";
import { assessGeneral } from "./generalModel";
import { addPending } from "./offlineQueue";
import { cachedApi } from "./patientCache";
import SavedCopyNote from "./SavedCopyNote";
import { ReminderNote } from "./AppointmentsPanel";
import { ReminderSummary } from "./ReminderPreference";
import InsurancePanel from "./InsurancePanel";
import HealerPanel from "./HealerPanel";
import ImmunisationPanel from "./ImmunisationPanel";
import PhotosPanel from "./PhotosPanel";

export default function PatientDetail({ t, user, patientId, syncTick, onQueued, onCall, onBack }) {
  const [data, setData] = useState(null);
  const [kind, setKind] = useState("general"); // general | antenatal
  const [latest, setLatest] = useState(null);
  const [formKey, setFormKey] = useState(0); // changing it clears the form
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [smsState, setSmsState] = useState({}); // observation id -> "sending" | "failed" | "noSms"
  const opened = useRef(false);

  const [savedAt, setSavedAt] = useState(null); // set when showing the phone's saved copy (no signal)

  // With signal: fresh page (and an encrypted copy is saved). Without: the saved copy.
  const fetchPatient = useCallback(
    () =>
      cachedApi(user.id, `/patients/${patientId}`).then((r) => {
        setData(r.data);
        setSavedAt(r.savedAt);
        return r.data;
      }),
    [user.id, patientId]
  );

  const load = () => fetchPatient().catch((err) => setError(err.message));

  useEffect(() => {
    fetchPatient()
      .then((d) => {
        // Pregnant patients open on the antenatal check (first load only, not after each sync)
        if (!opened.current) {
          opened.current = true;
          if (d.patient.pregnant) setKind("antenatal");
        }
      })
      .catch((err) => setError(err.message));
  }, [fetchPatient, syncTick]);

  const finish = (result) => {
    setLatest(result);
    setFormKey((k) => k + 1);
  };

  // No signal: check on the phone and queue it (encrypted) for the server
  const saveOffline = async (path, body) => {
    const local = kind === "general" ? assessGeneral(body) : predictRisk(data.patient.age, body);
    try {
      await addPending(user.id, { path, body: { ...body, recorded_at: new Date().toISOString() } });
    } catch (err) {
      return setError(err.message);
    }
    onQueued();
    finish({ ...local, offline: true });
  };

  const handleSubmit = async (body) => {
    setError("");
    setLoading(true);
    const path = kind === "general" ? `/patients/${patientId}/visit` : `/patients/${patientId}/assess`;

    if (!navigator.onLine) {
      await saveOffline(path, body);
    } else {
      try {
        const res = await api(path, { method: "POST", body });
        finish({
          risk_level: res.observation.risk_level,
          possible_conditions: res.observation.possible_conditions,
          advice: res.advice,
        });
        load();
      } catch (err) {
        // TypeError = the request never reached the server (weak signal)
        if (err instanceof TypeError) await saveOffline(path, body);
        else setError(err.message);
      }
    }
    setLoading(false);
  };

  const togglePregnancy = async () => {
    setError("");
    try {
      await api(`/patients/${patientId}/pregnancy`, { method: "POST", body: { pregnant: !data.patient.pregnant } });
      setKind(data.patient.pregnant ? "general" : "antenatal");
      load();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleReferral = async (obsId, reason = "") => {
    setSmsState({ ...smsState, [obsId]: "sending" });
    try {
      // The referral is saved even if the SMS fails; the facility sees it in its inbox
      const res = await api(`/observations/${obsId}/referral`, { method: "POST", body: { reason } });
      setSmsState({ ...smsState, [obsId]: res.sms_sent ? undefined : "noSms" });
      load();
    } catch {
      setSmsState({ ...smsState, [obsId]: "failed" });
    }
  };

  if (!data)
    return error ? (
      <>
        <button onClick={onBack} className="text-sm text-teal-700 hover:underline">← {t.back}</button>
        <p className="mt-3 text-red-600">{error}</p>
      </>
    ) : null;
  const { patient, observations, appointments = [] } = data;
  const canBePregnant = patient.sex === "female" && patient.age >= 10;

  return (
    <>
      <button onClick={onBack} className="text-sm text-teal-700 hover:underline">← {t.back}</button>
      {savedAt && <SavedCopyNote t={t} savedAt={savedAt} />}

      {/* Patient summary */}
      <div className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-gradient-to-r from-teal-800 to-teal-600 p-6 text-white">
        <div>
          <p className="font-mono text-sm text-amber-300">{patient.ref}</p>
          <h1 className="text-2xl font-bold">{patient.full_name}</h1>
          <p className="text-sm text-teal-100">
            {t[patient.sex] || ""} · {t.age} {patient.age}
            {patient.community && ` · ${patient.community}`}
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            {patient.pregnant ? (
              <span className="rounded-full bg-pink-200 px-2.5 py-0.5 text-xs font-semibold text-pink-900">{t.pregnantTag}</span>
            ) : null}
            {canBePregnant && (
              <button onClick={togglePregnancy} className="rounded-full border border-white/40 px-2.5 py-0.5 text-xs hover:bg-white/10">
                {patient.pregnant ? t.markNotPregnant : t.markPregnant}
              </button>
            )}
          </div>
        </div>
        <RiskBadge level={observations[0]?.risk_level} t={t} />
      </div>
      <ReminderSummary t={t} patient={patient} onChanged={load} />
      <InsurancePanel t={t} patientId={patient.id} />
      <HealerPanel t={t} patientId={patient.id} />
      {(patient.age < 5 || patient.birth_date) && <ImmunisationPanel t={t} patientId={patient.id} />}
      <PhotosPanel t={t} patientId={patient.id} userId={user.id} />

      {appointments.length > 0 && (
        <div className="mt-4 rounded-2xl border border-teal-200 bg-teal-50 p-4">
          <p className="text-sm font-semibold text-teal-900">📅 {t.upcomingAppointments}</p>
          {appointments.map((a) => (
            <p key={a.id} className="mt-1 text-sm text-teal-900">
              {a.scheduled_at} · {a.facility}
              {a.reason && ` · ${a.reason}`} · <ReminderNote a={{ ...a, has_phone: patient.phone ? 1 : 0 }} t={t} />
            </p>
          ))}
        </div>
      )}

      <div className="mt-6 grid gap-6 lg:grid-cols-5">
        {/* New check */}
        <div className="rounded-2xl border border-stone-200 bg-white p-6 lg:col-span-3">
          <div className="flex gap-1 rounded-xl bg-stone-100 p-1">
            {[
              ["general", t.generalVisit],
              ["antenatal", t.antenatalCheck],
            ].map(([key, label]) => (
              <button
                key={key}
                onClick={() => {
                  setKind(key);
                  setLatest(null);
                }}
                disabled={key === "antenatal" && !patient.pregnant}
                className={`flex-1 rounded-lg py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-40 ${
                  kind === key ? "bg-white text-teal-800 shadow" : "text-stone-600"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          {!patient.pregnant && <p className="mt-2 text-xs text-stone-500">{t.antenatalHint}</p>}

          <div className="mt-5">
            {kind === "general" ? (
              <GeneralVisitForm key={`g${formKey}`} t={t} loading={loading} onSubmit={handleSubmit} />
            ) : (
              <AntenatalForm key={`a${formKey}`} t={t} loading={loading} onSubmit={handleSubmit} />
            )}
          </div>

          {error && <p className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

          {latest && (
            <div className={`mt-5 rounded-xl p-4 ring-1 ${RISK_STYLE[latest.risk_level]}`}>
              <p className="text-lg font-bold">
                {t.riskLevel}: {latest.risk_level}
              </p>
              <p className="mt-1 text-sm">{latest.advice}</p>
              <ConditionChips conditions={latest.possible_conditions} t={t} />
              {latest.possible_conditions?.length > 0 && <p className="mt-1 text-xs opacity-80">{t.possibleNote}</p>}
              {latest.offline && <p className="mt-2 text-xs font-medium">{t.offlineResult}</p>}
            </div>
          )}
        </div>

        {/* History */}
        <div className="lg:col-span-2">
          <h2 className="text-lg font-semibold text-stone-800">{t.history}</h2>
          <div className="mt-4 space-y-3">
            {observations.length === 0 && <p className="text-sm text-stone-500">{t.noHistory}</p>}
            {observations.map((o) => (
              <div key={o.id} className="rounded-2xl border border-stone-200 bg-white p-4">
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <p className="text-xs font-semibold text-stone-700">
                      {o.visit_type === "general" ? t.generalVisit : t.antenatalCheck}
                    </p>
                    <p className="text-xs text-stone-500">{o.created_at}</p>
                  </div>
                  <RiskBadge level={o.risk_level} t={t} />
                </div>
                <VisitSummary o={o} t={t} />

                {o.referral_sent ? (
                  <ReferralChain o={o} t={t} noSms={smsState[o.id] === "noSms"} onCall={() => onCall(o.referral_id, patient.full_name)} />
                ) : (
                  (o.risk_level === "HIGH" || o.risk_level === "MEDIUM") && (
                    <ReferButton
                      o={o}
                      t={t}
                      sending={smsState[o.id] === "sending"}
                      failed={smsState[o.id] === "failed"}
                      onRefer={(reason) => handleReferral(o.id, reason)}
                    />
                  )
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}

// HIGH: refer straight away. MEDIUM: the CHV may refer, but must say why.
function ReferButton({ o, t, sending, failed, onRefer }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const isHigh = o.risk_level === "HIGH";

  if (!isHigh && !open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="mt-3 w-full rounded-xl border border-amber-300 bg-amber-50 py-2 text-sm font-semibold text-amber-900 hover:bg-amber-100"
      >
        {t.referMedium}
      </button>
    );
  }
  return (
    <>
      {!isHigh && (
        <textarea
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          rows={2}
          maxLength={300}
          placeholder={t.mediumReasonPlaceholder}
          className={`${inputClass} mt-3`}
        />
      )}
      <button
        onClick={() => onRefer(reason)}
        disabled={sending || (!isHigh && !reason.trim())}
        className="mt-3 w-full rounded-xl bg-red-600 py-2 text-sm font-semibold text-white hover:bg-red-700 disabled:opacity-50"
      >
        {sending ? t.sending : t.sendReferral}
      </button>
      {failed && <p className="mt-2 text-xs text-red-600">{t.referralFailed}</p>}
    </>
  );
}

// Health centre status, then the hospital step if the nurse referred onward
function ReferralChain({ o, t, noSms, onCall }) {
  return (
    <div className="mt-3 space-y-2">
      <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${REFERRAL_STYLE[o.referral_status]}`}>
        {t["referral_" + o.referral_status]}
      </span>
      {o.referral_reason && (
        <p className="text-xs text-stone-600">
          {t.reason}: {o.referral_reason}
        </p>
      )}
      {o.referral_outcome && <p className="text-sm text-stone-700">{o.referral_outcome}</p>}
      {o.escalated_to && (
        <div className="rounded-xl border border-violet-200 bg-violet-50 p-2">
          <p className="text-xs font-semibold text-violet-800">
            → {t.referredOnTo} {o.escalated_to}
          </p>
          <span className={`mt-1 inline-block rounded-full px-2.5 py-1 text-xs font-semibold ${REFERRAL_STYLE[o.escalated_status]}`}>
            {t["referral_" + o.escalated_status]}
          </span>
          {o.escalated_outcome && <p className="mt-1 text-sm text-stone-700">{o.escalated_outcome}</p>}
        </div>
      )}
      {noSms && <p className="text-xs text-amber-700">{t.smsNotDelivered}</p>}
      {o.referral_id && (
        <button onClick={onCall} className="block text-sm font-medium text-teal-700 hover:underline">
          📹 {t.videoCall}
        </button>
      )}
    </div>
  );
}

// One line of key readings, different for each kind of check
export function VisitSummary({ o, t }) {
  if (o.visit_type !== "general") {
    return (
      <p className="mt-2 text-sm text-stone-700">
        BP {o.systolic_bp}/{o.diastolic_bp} · Hb {o.hemoglobin} · {o.gestational_age} wks
        {o.weight != null && ` · ${o.weight} kg`}
        {o.height != null && ` · ${o.height} cm`}
      </p>
    );
  }
  const readings = [
    o.body_temp != null && `${o.body_temp}°C`,
    o.systolic_bp != null && `BP ${o.systolic_bp}/${o.diastolic_bp ?? "?"}`,
    o.heart_rate != null && `${o.heart_rate} bpm`,
    o.weight != null && `${o.weight} kg`,
    o.height != null && `${o.height} cm`,
  ].filter(Boolean);
  const symptoms = (o.symptoms || "").split(",").filter(Boolean).map((s) => t["sym_" + s] || s);
  return (
    <>
      {readings.length > 0 && <p className="mt-2 text-sm text-stone-700">{readings.join(" · ")}</p>}
      {symptoms.length > 0 && <p className="mt-1 text-sm text-stone-600">{symptoms.join(", ")}</p>}
      <ConditionChips conditions={o.possible_conditions} t={t} />
      {o.notes && <p className="mt-1 text-xs italic text-stone-500">{o.notes}</p>}
    </>
  );
}
