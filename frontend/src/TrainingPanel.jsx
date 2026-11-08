import { useState, useEffect, useCallback } from "react";
import { api } from "./api";
import { cachedApi } from "./patientCache";
import LessonSlides from "./LessonSlides";
import FeePayment from "./FeePayment";
import { inputClass } from "./styles";

const STATUS_STYLE = {
  valid: "bg-emerald-100 text-emerald-800",
  expiring: "bg-amber-100 text-amber-800",
  expired: "bg-stone-200 text-stone-700",
  revoked: "bg-red-100 text-red-700",
};
const day = (text) => text.slice(0, 10);

function StatusBadge({ t, status }) {
  return <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${STATUS_STYLE[status]}`}>{t["cert_" + status]}</span>;
}

function expiryText(t, cert) {
  if (cert.status === "revoked") return `${t.certRevokedReason}: ${cert.revoke_reason}`;
  if (cert.status === "expired") return `${t.certExpiredOn} ${day(cert.expires_at)}`;
  return `${t.certExpiresOn} ${day(cert.expires_at)} (${cert.days_left} ${t.certDaysLeft})`;
}

function Certificate({ t, cert }) {
  return (
    <div className="rounded-xl border border-teal-200 bg-teal-50/50 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-semibold text-stone-900">🎓 {cert.title}</p>
        <StatusBadge t={t} status={cert.status} />
      </div>
      <p className="mt-1 text-xs text-stone-600">{t.certCode}: <span className="font-mono">{cert.code}</span> · {t.certIssuedOn} {day(cert.issued_at)}</p>
      <p className="text-xs text-stone-600">{expiryText(t, cert)}</p>
      {cert.source === "ghs" && <p className="text-xs text-stone-600">{t.certIssuedBy} {cert.issued_by_name}: {cert.note}</p>}
      <p className="mt-1 text-[11px] italic text-stone-500">{t.certDisclaimer}</p>
    </div>
  );
}

function Quiz({ t, module, passPercent, onDone }) {
  const [answers, setAnswers] = useState({});
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const complete = module.questions.every((_, i) => answers[i] !== undefined);

  const submit = async () => {
    setError("");
    try {
      const body = { answers: module.questions.map((_, i) => answers[i]) };
      const res = await api(`/training/modules/${module.code}/attempt`, { method: "POST", body });
      setResult(res);
      setAnswers({});
      onDone();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="mt-3 space-y-3">
      <p className="text-xs text-stone-500">{t.quizHint} {passPercent}%.</p>
      {module.questions.map((q, i) => (
        <fieldset key={q.text}>
          <legend className="font-medium text-stone-800">{i + 1}. {q.text}</legend>
          {q.options.map((option, choice) => (
            <label key={option} className="mt-1 flex items-center gap-2 text-stone-700">
              <input type="radio" name={`${module.code}-${i}`} checked={answers[i] === choice} onChange={() => setAnswers({ ...answers, [i]: choice })} />
              {option}
            </label>
          ))}
        </fieldset>
      ))}
      <button onClick={submit} disabled={!complete} className="rounded-xl bg-teal-700 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-800 disabled:opacity-50">
        {t.quizSubmit}
      </button>
      {error && <p className="text-sm text-red-600">{error}</p>}
      {result && (
        <p className={`rounded-lg px-3 py-2 text-sm ${result.passed ? "bg-emerald-50 text-emerald-800" : "bg-amber-50 text-amber-800"}`}>
          {t.quizScore}: {result.score} / {result.total}. {result.passed ? t.quizPassed : t.quizFailed}
        </p>
      )}
    </div>
  );
}

// Every health worker's own training: modules, quiz, progress and certificates
export default function TrainingPanel({ t, role, userId }) {
  const [data, setData] = useState(null);
  const [open, setOpen] = useState(false);
  const [shown, setShown] = useState(null);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    cachedApi(userId, "/training/modules").then((r) => setData(r.data)).catch(() => setData(null));
  }, [userId]);
  useEffect(load, [load]);

  if (!data) return null;
  const current = data.modules.filter((m) => ["valid", "expiring"].includes(m.certificate?.status)).length;
  const canReview = role === "nurse" || role === "doctor";

  const approve = async (code) => {
    setError("");
    try {
      await api(`/training/modules/${code}/review`, { method: "POST" });
      load();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="mt-6 rounded-2xl border border-stone-200 bg-white p-5 text-sm">
      <button onClick={() => setOpen(!open)} className="text-lg font-semibold text-stone-800">
        {open ? "▾" : "▸"} 🎓 {t.trainingTitle}
      </button>
      <p className="mt-1 text-xs text-stone-500">{t.trainingProgress}: {current} / {data.modules.length}</p>
      {open && (
        <div className="mt-3 space-y-2">
          <div className="h-2 overflow-hidden rounded-full bg-stone-100">
            <div className="h-full bg-teal-700" style={{ width: `${(current / data.modules.length) * 100}%` }} />
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}

          {data.modules.map((m) => {
            const status = m.certificate?.status;
            const canTake = m.reviewed_at && status !== "valid" && status !== "revoked";
            return (
              <div key={m.code} className="rounded-xl border border-stone-200 p-3">
                <button onClick={() => setShown(shown === m.code ? null : m.code)} className="flex w-full flex-wrap items-center justify-between gap-2 text-left">
                  <span className="font-semibold text-stone-900">{m.title}</span>
                  {status ? <StatusBadge t={t} status={status} /> : <span className="text-xs text-stone-500">{t.trainingNotDone}</span>}
                </button>
                {m.tries > 0 && <p className="mt-1 text-xs text-stone-500">{t.trainingBest}: {m.best_score} / {m.questions.length} · {t.trainingTries}: {m.tries}</p>}
                {shown === m.code && (
                  <div className="mt-2 space-y-2">
                    <LessonSlides t={t} body={m.body} />
                    {m.certificate && <Certificate t={t} cert={m.certificate} />}
                    {!m.reviewed_at && <p className="rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800">{t.trainingNeedsReview}</p>}
                    {m.reviewer_name && <p className="text-xs text-stone-500">{t.lessonsReviewedBy} {m.reviewer_name}</p>}
                    {canReview && !m.reviewed_at && (
                      <button onClick={() => approve(m.code)} className="rounded-xl border border-stone-300 px-3 py-1.5 text-xs font-medium text-stone-700 hover:bg-stone-100">
                        {t.lessonsApprove}
                      </button>
                    )}
                    {status === "revoked" && <p className="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700">{t.trainingRevokedHint}</p>}
                    {status === "valid" && <p className="text-xs text-stone-500">{t.trainingRenewLater} {data.expiring_days} {t.certDaysLeft}.</p>}
                    {canTake && m.fee_due && <FeePayment t={t} kind="training" item={m.code} label={t.feeTraining} onPaid={load} />}
                    {canTake && !m.fee_due && <Quiz t={t} module={m} passPercent={data.pass_percent} onDone={load} />}
                  </div>
                )}
              </div>
            );
          })}

          {data.certificates.length > 0 && (
            <div className="space-y-2 pt-2">
              <p className="font-semibold text-stone-800">{t.trainingMyCertificates}</p>
              {data.certificates.map((c) => <Certificate key={c.id} t={t} cert={c} />)}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

const FILTERS = ["all", "valid", "expiring", "expired", "revoked", "no_certificate"];

// GHS officer: every health worker's certificates, with issue and revoke
export function WorkerCertificates({ t }) {
  const [data, setData] = useState(null);
  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [action, setAction] = useState(null); // { type: "issue", worker } or { type: "revoke", cert }
  const [module, setModule] = useState("");
  const [text, setText] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(() => {
    api("/training/workers").then(setData).catch((err) => setError(err.message));
  }, []);
  useEffect(load, [load]);

  if (!data) return error ? <p className="mt-4 text-sm text-red-600">{error}</p> : null;

  const needle = search.trim().toLowerCase();
  const workers = data.workers.filter((w) => {
    const words = [w.full_name, w.facility, w.district, ...w.certificates.map((c) => c.code)].join(" ").toLowerCase();
    if (needle && !words.includes(needle)) return false;
    if (filter === "all") return true;
    if (filter === "no_certificate") return w.certificates.length === 0;
    return w.certificates.some((c) => c.status === filter);
  });

  const start = (next) => {
    setAction(next);
    setModule(data.modules[0].code);
    setText("");
    setError("");
  };

  const save = async () => {
    setError("");
    try {
      if (action.type === "issue") {
        await api(`/training/workers/${action.worker}/certificates`, { method: "POST", body: { module, note: text } });
      } else {
        await api(`/training/certificates/${action.cert}/revoke`, { method: "POST", body: { reason: text } });
      }
      setAction(null);
      load();
    } catch (err) {
      setError(err.message);
    }
  };

  const form = (
    <div className="mt-2 space-y-2 rounded-xl border border-teal-200 bg-teal-50/50 p-3">
      {action?.type === "issue" && (
        <select value={module} onChange={(e) => setModule(e.target.value)} className={inputClass}>
          {data.modules.map((m) => <option key={m.code} value={m.code}>{m.title}</option>)}
        </select>
      )}
      <input placeholder={action?.type === "issue" ? t.certIssueNote : t.certRevokeReason} value={text} onChange={(e) => setText(e.target.value)} className={inputClass} />
      <div className="flex gap-2">
        <button onClick={save} disabled={text.trim().length < 5} className="rounded-xl bg-teal-700 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-800 disabled:opacity-50">
          {action?.type === "issue" ? t.certIssue : t.certRevoke}
        </button>
        <button onClick={() => setAction(null)} className="rounded-xl border border-stone-300 px-4 py-2 text-sm font-medium text-stone-700 hover:bg-stone-100">{t.certCancel}</button>
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
    </div>
  );

  return (
    <div className="mt-6 rounded-2xl border border-stone-200 bg-white p-5 text-sm">
      <button onClick={() => setOpen(!open)} className="text-lg font-semibold text-stone-800">
        {open ? "▾" : "▸"} 🎓 {t.certGhsTitle}
      </button>
      <p className="mt-1 text-xs text-stone-500">{t.certGhsHint}</p>
      {open && (
        <div className="mt-3 space-y-3">
          <div className="flex flex-wrap gap-2">
            {FILTERS.map((f) => (
              <button key={f} onClick={() => setFilter(f)} className={`rounded-full border px-3 py-1 text-xs font-medium ${filter === f ? "border-teal-700 bg-teal-700 text-white" : "border-stone-300 text-stone-700 hover:bg-stone-100"}`}>
                {t["cert_" + f]}{f === "all" ? "" : ` (${data.summary[f]})`}
              </button>
            ))}
          </div>
          <input placeholder={t.certSearch} value={search} onChange={(e) => setSearch(e.target.value)} className={inputClass} />
          {workers.length === 0 && <p className="text-stone-500">{t.certNoWorkers}</p>}

          {workers.map((w) => (
            <div key={w.id} className="rounded-xl border border-stone-200 p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="font-semibold text-stone-900">{w.full_name}</p>
                  <p className="text-xs text-stone-500">{t["role_" + w.role] || w.role} · {w.facility || "-"} · {w.district || "-"}</p>
                </div>
                <button onClick={() => start({ type: "issue", worker: w.id })} className="font-medium text-teal-700 hover:underline">+ {t.certIssue}</button>
              </div>
              {action?.worker === w.id && form}
              {w.certificates.map((c) => (
                <div key={c.id} className="mt-2 border-t border-stone-100 pt-2">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-medium text-stone-800">{c.title}</span>
                    <span className="flex items-center gap-2">
                      <StatusBadge t={t} status={c.status} />
                      {c.status !== "revoked" && <button onClick={() => start({ type: "revoke", cert: c.id })} className="text-xs font-medium text-red-700 hover:underline">{t.certRevoke}</button>}
                    </span>
                  </div>
                  <p className="text-xs text-stone-500"><span className="font-mono">{c.code}</span> · {expiryText(t, c)}</p>
                  {action?.cert === c.id && form}
                </div>
              ))}
            </div>
          ))}
          <p className="text-[11px] italic text-stone-500">{t.certDisclaimer}</p>
        </div>
      )}
    </div>
  );
}
