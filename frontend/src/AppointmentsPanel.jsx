import { useState, useEffect } from "react";
import { api } from "./api";
import { inputClass } from "./styles";
import FeePayment from "./FeePayment";

// Upcoming appointments at this facility (nurse / doctor), soonest first
export function AppointmentsPanel({ t, refreshKey }) {
  const [appointments, setAppointments] = useState([]);
  const [error, setError] = useState("");

  const load = () => api("/appointments").then(setAppointments).catch((err) => setError(err.message));

  useEffect(() => {
    api("/appointments").then(setAppointments).catch((err) => setError(err.message));
  }, [refreshKey]);

  const mark = async (id, status) => {
    try {
      await api(`/appointments/${id}/status`, { method: "POST", body: { status } });
      load();
    } catch (err) {
      setError(err.message);
    }
  };

  // Ghana time = UTC, same format as the server: "YYYY-MM-DD HH:MM"
  const nowText = new Date().toISOString().slice(0, 16).replace("T", " ");

  return (
    <div className="mt-5 rounded-2xl border border-stone-200 bg-white p-5">
      <h2 className="text-lg font-semibold text-stone-800">
        {t.upcomingAppointments} ({appointments.length})
      </h2>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
      {appointments.length === 0 && <p className="mt-2 text-sm text-stone-500">{t.noAppointments}</p>}
      <div className="mt-3 divide-y divide-stone-100">
        {appointments.map((a) => (
          <div
            key={a.id}
            className={`flex flex-wrap items-center justify-between gap-2 py-3 ${a.scheduled_at < nowText ? "-mx-2 rounded-lg bg-red-50 px-2" : ""}`}
          >
            <div>
              {/* Time has passed but nobody updated it: nudge staff to mark attended or missed */}
              {a.scheduled_at < nowText && <p className="text-xs font-semibold text-red-700">⏰ {t.overdue}</p>}
              <p className="font-medium text-stone-800">
                {a.scheduled_at} · {a.full_name} <span className="font-mono text-xs text-stone-500">{a.ref}</span>
              </p>
              <p className="text-xs text-stone-500">
                {a.reason && `${a.reason} · `}
                {t.bookedBy} {a.booked_by_name} · <ReminderNote a={a} t={t} />
              </p>
              <div className="mt-1"><FeePayment t={t} kind="consultation" item={a.id} label={t.feeConsultation} /></div>
            </div>
            <div className="flex gap-1">
              {["attended", "missed", "cancelled"].map((s) => (
                <button
                  key={s}
                  onClick={() => mark(a.id, s)}
                  className="rounded-lg border border-stone-300 px-2.5 py-1 text-xs text-stone-700 hover:bg-stone-100"
                >
                  {t["appt_" + s]}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// What happened (or will happen) with the SMS reminder
export function ReminderNote({ a, t }) {
  if (a.reminder_status === "sent") return <span className="text-emerald-700">{t.reminderSent}</span>;
  if (a.reminder_status === "failed") return <span className="text-red-600">{t.reminderFailed}</span>;
  if (a.reminder_status === "chv") return <span className="text-amber-700">{t.chvRemind}</span>;
  if (a.reminder_status === "no_phone" || a.has_phone === 0) return <span className="text-amber-700">{t.noPhoneRemind}</span>;
  return <span>{t.reminderPending}</span>;
}

// "Book follow-up" form on a referral card
export function BookAppointment({ referralId, t, onBooked }) {
  const [open, setOpen] = useState(false);
  const [when, setWhen] = useState("");
  const [reason, setReason] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const book = async () => {
    setError("");
    try {
      const res = await api(`/referrals/${referralId}/appointments`, { method: "POST", body: { scheduled_at: when, reason } });
      setResult(res);
      setOpen(false);
      setWhen("");
      setReason("");
      onBooked();
    } catch (err) {
      setError(err.message);
    }
  };

  // Earliest choosable time = now (Ghana time = UTC, same as the server)
  const minTime = new Date().toISOString().slice(0, 16);

  return (
    <div className="mt-3">
      {result && (
        <p className="mb-2 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
          ✓ {t.bookedFor} {result.scheduled_at} ·{" "}
          {result.reminder_method !== "sms" ? t.chvRemind : result.has_phone ? (result.sms_sent ? t.confirmSent : t.confirmFailed) : t.noPhoneRemind}
        </p>
      )}
      {!open ? (
        <button onClick={() => setOpen(true)} className="text-sm font-medium text-teal-700 hover:underline">
          {t.bookFollowUp}
        </button>
      ) : (
        <div className="space-y-2 rounded-xl border border-teal-200 bg-teal-50/50 p-3">
          <input type="datetime-local" min={minTime} value={when} onChange={(e) => setWhen(e.target.value)} className={inputClass} />
          <input value={reason} onChange={(e) => setReason(e.target.value)} maxLength={200} placeholder={t.apptReasonPlaceholder} className={inputClass} />
          {error && <p className="text-sm text-red-600">{error}</p>}
          <div className="flex gap-2">
            <button
              onClick={book}
              disabled={!when}
              className="rounded-xl bg-teal-700 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-800 disabled:opacity-50"
            >
              {t.book}
            </button>
            <button onClick={() => setOpen(false)} className="rounded-xl px-4 py-2 text-sm text-stone-600 hover:bg-stone-100">
              {t.cancel}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
