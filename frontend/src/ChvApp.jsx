import { useState, useEffect } from "react";
import { api } from "./api";
import Header from "./Header";
import RiskBadge from "./RiskBadge";
import PatientDetail from "./PatientDetail";
import { inputClass } from "./styles";
import { getPending, syncPending } from "./offlineQueue";

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
            key={selectedId}
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
                <p className="font-semibold text-stone-800">
                  {p.full_name}
                  {p.pregnant ? (
                    <span className="ml-2 rounded-full bg-pink-100 px-2 py-0.5 align-middle text-xs font-medium text-pink-800">{t.pregnantTag}</span>
                  ) : null}
                </p>
                <p className="text-xs text-stone-500">
                  <span className="font-mono">{p.ref}</span> · {t[p.sex] || ""} · {t.age} {p.age}
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
  const [form, setForm] = useState({ full_name: "", age: "", sex: "", pregnant: false, phone: "", community: "", consent: false });
  const canBePregnant = form.sex === "female" && Number(form.age) >= 10;
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.consent) return setError(t.consentRequired);
    setSaving(true);
    try {
      const patient = await api("/patients", {
        method: "POST",
        body: { ...form, age: Number(form.age), pregnant: canBePregnant && form.pregnant },
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
            <input required type="number" min="0" max="120" value={form.age} onChange={(e) => setForm({ ...form, age: e.target.value })} className={inputClass} />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-stone-700">{t.sex}</label>
            <select required value={form.sex} onChange={(e) => setForm({ ...form, sex: e.target.value })} className={inputClass}>
              <option value="" disabled>–</option>
              <option value="female">{t.female}</option>
              <option value="male">{t.male}</option>
            </select>
          </div>
        </div>
        {canBePregnant && (
          <label className="flex cursor-pointer items-center gap-3 rounded-xl border border-pink-200 bg-pink-50 p-3 text-sm text-pink-900">
            <input
              type="checkbox"
              checked={form.pregnant}
              onChange={(e) => setForm({ ...form, pregnant: e.target.checked })}
              className="h-5 w-5 accent-pink-600"
            />
            {t.pregnantNow}
          </label>
        )}
        <div>
          <label className="mb-1 block text-sm font-medium text-stone-700">{t.community}</label>
          <input value={form.community} onChange={(e) => setForm({ ...form, community: e.target.value })} className={inputClass} />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-stone-700">{t.patientPhone}</label>
          <input
            type="tel"
            inputMode="numeric"
            placeholder="0240000000"
            value={form.phone}
            onChange={(e) => setForm({ ...form, phone: e.target.value })}
            className={inputClass}
          />
          <p className="mt-1 text-xs text-stone-500">{t.patientPhoneHint}</p>
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
