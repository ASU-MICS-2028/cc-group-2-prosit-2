import { useState, useEffect } from "react";
import { api } from "./api";
import Header from "./Header";
import { predictRisk } from "./riskModel";
import { addPending, getPending, syncPending } from "./offlineQueue";

const RISK_STYLE = {
  HIGH: "bg-red-100 text-red-700 ring-red-200",
  MEDIUM: "bg-amber-100 text-amber-800 ring-amber-200",
  LOW: "bg-emerald-100 text-emerald-700 ring-emerald-200",
};

// field name, unit, example value (shown as placeholder)
const VITALS = [
  ["gestational_age", "weeks", "28"],
  ["systolic_bp", "mmHg", "120"],
  ["diastolic_bp", "mmHg", "80"],
  ["weight", "kg", "65"],
  ["hemoglobin", "g/dL", "11.5"],
  ["body_temp", "°C", "36.8"],
  ["heart_rate", "bpm", "80"],
];

const inputClass =
  "w-full rounded-xl border border-stone-300 bg-white px-4 py-3 text-sm outline-none transition focus:border-teal-600 focus:ring-4 focus:ring-teal-100";

function RiskBadge({ level, t }) {
  if (!level) return <span className="rounded-full bg-stone-100 px-2.5 py-1 text-xs text-stone-500">{t.notAssessed}</span>;
  return (
    <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ${RISK_STYLE[level]}`}>{level}</span>
  );
}

export default function ChvApp(props) {
  const { t, user } = props;
  const [view, setView] = useState("list"); // list | register | patient
  const [patients, setPatients] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [pendingCount, setPendingCount] = useState(() => getPending(user.id).length);
  const [syncTick, setSyncTick] = useState(0); // bumps after a sync so screens reload

  const loadPatients = () => api("/patients").then(setPatients).catch(() => {});

  useEffect(() => {
    // Send any offline checks now, and again whenever signal comes back
    const sync = () =>
      syncPending(user.id).then(() => {
        setPendingCount(getPending(user.id).length);
        setSyncTick((n) => n + 1);
        loadPatients();
      });
    sync();
    window.addEventListener("online", sync);
    return () => window.removeEventListener("online", sync);
  }, [user.id]);

  const openPatient = (id) => {
    setSelectedId(id);
    setView("patient");
  };

  const goToList = () => {
    loadPatients();
    setView("list");
  };

  return (
    <div className="min-h-screen bg-stone-50">
      <Header {...props} />
      <main className="mx-auto max-w-5xl px-4 py-6">
        {pendingCount > 0 && (
          <div className="mb-5 flex items-center gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            <span className="h-2 w-2 animate-pulse rounded-full bg-amber-500" />
            {pendingCount} {t.pendingSync}
          </div>
        )}
        {view === "list" && (
          <PatientList t={t} patients={patients} onOpen={openPatient} onRegister={() => setView("register")} />
        )}
        {view === "register" && <RegisterPatient t={t} onDone={openPatient} onBack={goToList} />}
        {view === "patient" && (
          <PatientDetail
            t={t}
            user={user}
            patientId={selectedId}
            syncTick={syncTick}
            onQueued={() => setPendingCount(getPending(user.id).length)}
            onBack={goToList}
          />
        )}
        <p className="mt-12 text-center text-xs text-stone-400">{t.builtBy}</p>
      </main>
    </div>
  );
}

function PatientList({ t, patients, onOpen, onRegister }) {
  const [query, setQuery] = useState("");
  const count = (level) => patients.filter((p) => p.latest_risk === level).length;
  const shown = patients.filter((p) =>
    (p.full_name + " " + p.ref).toLowerCase().includes(query.toLowerCase())
  );

  const stats = [
    [t.total, patients.length, "text-stone-800"],
    [t.high, count("HIGH"), "text-red-600"],
    [t.medium, count("MEDIUM"), "text-amber-600"],
    [t.low, count("LOW"), "text-emerald-600"],
  ];

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h1 className="text-2xl font-bold text-stone-800">{t.patients}</h1>
        <button
          onClick={onRegister}
          className="rounded-xl bg-teal-700 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-teal-700/20 hover:bg-teal-800"
        >
          + {t.register}
        </button>
      </div>

      <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {stats.map(([label, value, color]) => (
          <div key={label} className="rounded-2xl border border-stone-200 bg-white p-4">
            <p className="text-xs font-medium text-stone-500">{label}</p>
            <p className={`mt-1 text-3xl font-bold ${color}`}>{value}</p>
          </div>
        ))}
      </div>

      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder={t.search}
        className={`${inputClass} mt-5`}
      />

      <div className="mt-4 space-y-2">
        {shown.length === 0 && (
          <div className="rounded-2xl border border-dashed border-stone-300 bg-white p-10 text-center text-sm text-stone-500">
            {t.noPatients}
          </div>
        )}
        {shown.map((p) => (
          <button
            key={p.id}
            onClick={() => onOpen(p.id)}
            className="flex w-full items-center justify-between rounded-2xl border border-stone-200 bg-white p-4 text-left transition hover:border-teal-300 hover:shadow-md"
          >
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-teal-50 font-semibold text-teal-700">
                {p.full_name.charAt(0).toUpperCase()}
              </div>
              <div>
                <p className="font-semibold text-stone-800">{p.full_name}</p>
                <p className="text-xs text-stone-500">
                  <span className="font-mono">{p.ref}</span> · {t.age} {p.age}
                  {p.community && ` · ${p.community}`}
                </p>
              </div>
            </div>
            <RiskBadge level={p.latest_risk} t={t} />
          </button>
        ))}
      </div>
    </>
  );
}

function RegisterPatient({ t, onDone, onBack }) {
  const [form, setForm] = useState({ full_name: "", age: "", community: "", consent: false });
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.consent) return setError(t.consentRequired);
    setSaving(true);
    try {
      const patient = await api("/patients", {
        method: "POST",
        body: { ...form, age: Number(form.age) },
      });
      onDone(patient.id);
    } catch (err) {
      setError(err.message);
    }
    setSaving(false);
  };

  return (
    <div className="mx-auto max-w-lg">
      <button onClick={onBack} className="text-sm text-teal-700 hover:underline">← {t.back}</button>
      <h1 className="mt-3 text-2xl font-bold text-stone-800">{t.register}</h1>

      <form onSubmit={handleSubmit} className="mt-5 space-y-4 rounded-2xl border border-stone-200 bg-white p-6">
        <div>
          <label className="mb-1 block text-sm font-medium text-stone-700">{t.fullName}</label>
          <input required value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} className={inputClass} />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1 block text-sm font-medium text-stone-700">{t.age}</label>
            <input required type="number" min="10" max="60" value={form.age} onChange={(e) => setForm({ ...form, age: e.target.value })} className={inputClass} />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-stone-700">{t.community}</label>
            <input value={form.community} onChange={(e) => setForm({ ...form, community: e.target.value })} className={inputClass} />
          </div>
        </div>

        <label className="flex cursor-pointer items-start gap-3 rounded-xl bg-teal-50 p-4 text-sm text-teal-900">
          <input
            type="checkbox"
            checked={form.consent}
            onChange={(e) => setForm({ ...form, consent: e.target.checked })}
            className="mt-0.5 h-5 w-5 accent-teal-700"
          />
          {t.consentLabel}
        </label>

        {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

        <button
          type="submit"
          disabled={saving}
          className="w-full rounded-xl bg-teal-700 py-3 font-semibold text-white hover:bg-teal-800 disabled:opacity-60"
        >
          {saving ? t.saving : t.save}
        </button>
      </form>
    </div>
  );
}

function PatientDetail({ t, user, patientId, syncTick, onQueued, onBack }) {
  const [data, setData] = useState(null);
  const [vitals, setVitals] = useState({ previous_complications: false });
  const [latest, setLatest] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [smsState, setSmsState] = useState({}); // observation id -> "sending" | "failed"

  const load = () => api(`/patients/${patientId}`).then(setData).catch((err) => setError(err.message));

  useEffect(() => {
    api(`/patients/${patientId}`).then(setData).catch((err) => setError(err.message));
  }, [patientId, syncTick]);

  // No signal: score on the phone and queue the check for the server
  const assessOffline = async (body) => {
    const local = predictRisk(data.patient.age, body);
    try {
      await addPending(user.id, { patientId, body: { ...body, recorded_at: new Date().toISOString() } });
    } catch (err) {
      return setError(err.message);
    }
    onQueued();
    setLatest({ observation: { risk_level: local.risk_level }, advice: local.advice, offline: true });
    setVitals({ previous_complications: false });
  };

  const handleAssess = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    const body = { previous_complications: vitals.previous_complications };
    VITALS.forEach(([name]) => (body[name] = Number(vitals[name])));

    if (!navigator.onLine) {
      await assessOffline(body);
    } else {
      try {
        const result = await api(`/patients/${patientId}/assess`, { method: "POST", body });
        setLatest(result);
        setVitals({ previous_complications: false });
        load();
      } catch (err) {
        // TypeError = the request never reached the server (weak signal)
        if (err instanceof TypeError) await assessOffline(body);
        else setError(err.message);
      }
    }
    setLoading(false);
  };

  const handleReferral = async (obsId) => {
    setSmsState({ ...smsState, [obsId]: "sending" });
    try {
      const res = await api(`/observations/${obsId}/referral`, { method: "POST" });
      setSmsState({ ...smsState, [obsId]: res.success ? undefined : "failed" });
      if (res.success) load();
    } catch {
      setSmsState({ ...smsState, [obsId]: "failed" });
    }
  };

  if (!data) return error ? <p className="text-red-600">{error}</p> : null;
  const { patient, observations } = data;

  return (
    <>
      <button onClick={onBack} className="text-sm text-teal-700 hover:underline">← {t.back}</button>

      {/* Patient summary */}
      <div className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-gradient-to-r from-teal-800 to-teal-600 p-6 text-white">
        <div>
          <p className="font-mono text-sm text-amber-300">{patient.ref}</p>
          <h1 className="text-2xl font-bold">{patient.full_name}</h1>
          <p className="text-sm text-teal-100">
            {t.age} {patient.age}{patient.community && ` · ${patient.community}`}
          </p>
        </div>
        <RiskBadge level={observations[0]?.risk_level} t={t} />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-5">
        {/* New check */}
        <form onSubmit={handleAssess} className="rounded-2xl border border-stone-200 bg-white p-6 lg:col-span-3">
          <h2 className="text-lg font-semibold text-stone-800">{t.newCheck}</h2>
          <div className="mt-4 grid grid-cols-2 gap-3">
            {VITALS.map(([name, unit, example]) => (
              <div key={name}>
                <label className="mb-1 block text-xs font-medium text-stone-600">{t[name]}</label>
                <div className="relative">
                  <input
                    required
                    type="number"
                    step="any"
                    placeholder={example}
                    value={vitals[name] ?? ""}
                    onChange={(e) => setVitals({ ...vitals, [name]: e.target.value })}
                    className={`${inputClass} pr-14`}
                  />
                  <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs text-stone-400">{unit}</span>
                </div>
              </div>
            ))}
          </div>
          <label className="mt-4 flex cursor-pointer items-center gap-3 text-sm text-stone-700">
            <input
              type="checkbox"
              checked={vitals.previous_complications}
              onChange={(e) => setVitals({ ...vitals, previous_complications: e.target.checked })}
              className="h-5 w-5 accent-teal-700"
            />
            {t.previous_complications}
          </label>

          {error && <p className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

          <button
            type="submit"
            disabled={loading}
            className="mt-5 w-full rounded-xl bg-teal-700 py-3 font-semibold text-white hover:bg-teal-800 disabled:opacity-60"
          >
            {loading ? t.assessing : t.assess}
          </button>

          {latest && (
            <div className={`mt-5 rounded-xl p-4 ring-1 ${RISK_STYLE[latest.observation.risk_level]}`}>
              <p className="text-lg font-bold">
                {t.riskLevel}: {latest.observation.risk_level}
              </p>
              <p className="mt-1 text-sm">{latest.advice}</p>
              {latest.offline && <p className="mt-2 text-xs font-medium">{t.offlineResult}</p>}
            </div>
          )}
        </form>

        {/* History */}
        <div className="lg:col-span-2">
          <h2 className="text-lg font-semibold text-stone-800">{t.history}</h2>
          <div className="mt-4 space-y-3">
            {observations.length === 0 && <p className="text-sm text-stone-500">{t.noHistory}</p>}
            {observations.map((o) => (
              <div key={o.id} className="rounded-2xl border border-stone-200 bg-white p-4">
                <div className="flex items-center justify-between">
                  <p className="text-xs text-stone-500">{o.created_at}</p>
                  <RiskBadge level={o.risk_level} t={t} />
                </div>
                <p className="mt-2 text-sm text-stone-700">
                  BP {o.systolic_bp}/{o.diastolic_bp} · Hb {o.hemoglobin} · {o.gestational_age} wks
                </p>
                {o.risk_level === "HIGH" &&
                  (o.referral_sent ? (
                    <p className="mt-3 text-sm font-medium text-emerald-700">✓ {t.referralSent}</p>
                  ) : (
                    <>
                      <button
                        onClick={() => handleReferral(o.id)}
                        disabled={smsState[o.id] === "sending"}
                        className="mt-3 w-full rounded-xl bg-red-600 py-2 text-sm font-semibold text-white hover:bg-red-700 disabled:opacity-60"
                      >
                        {smsState[o.id] === "sending" ? t.sending : t.sendReferral}
                      </button>
                      {smsState[o.id] === "failed" && <p className="mt-2 text-xs text-red-600">{t.referralFailed}</p>}
                    </>
                  ))}
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}
