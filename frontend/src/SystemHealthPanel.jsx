import { useState, useEffect } from "react";
import { api } from "./api";

const STATE = {
  OK: { dot: "bg-emerald-500", label: "healthOk", text: "text-emerald-700" },
  ALARM: { dot: "bg-red-600", label: "healthAlarm", text: "text-red-700" },
  INSUFFICIENT_DATA: { dot: "bg-stone-400", label: "healthChecking", text: "text-stone-500" },
};

// Admin: the CloudWatch alarms (server errors, server down, database busy / full).
// System information only, no patient data.
export default function SystemHealthPanel({ t }) {
  const [health, setHealth] = useState(null);
  const [error, setError] = useState("");

  const load = () => api("/admin/system-health").then(setHealth).catch((err) => setError(err.message));

  useEffect(() => {
    api("/admin/system-health").then(setHealth).catch((err) => setError(err.message));
  }, []);

  if (!health && !error) return null;
  const firing = health?.alarms.filter((a) => a.state === "ALARM").length || 0;

  return (
    <div className={`mt-6 rounded-2xl border bg-white p-5 ${firing ? "border-red-300 ring-2 ring-red-100" : "border-stone-200"}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-semibold text-stone-800">🩺 {t.healthTitle}</h2>
        {health?.available && (
          <button onClick={load} className="text-sm font-medium text-teal-700 hover:underline">
            ↻ {t.healthRefresh}
          </button>
        )}
      </div>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
      {health && !health.available && (
        <p className="mt-2 text-sm text-stone-500">{health.error ? t.healthUnreachable : t.healthLocalOnly}</p>
      )}
      {health?.available && (
        <>
          <p className={`mt-1 text-sm font-medium ${firing ? "text-red-700" : "text-emerald-700"}`}>
            {firing ? `${firing} ${t.healthFiring}` : t.healthAllOk}
          </p>
          <ul className="mt-3 divide-y divide-stone-100">
            {health.alarms.map((a) => {
              const s = STATE[a.state] || STATE.INSUFFICIENT_DATA;
              return (
                <li key={a.name} className="flex items-start gap-3 py-2">
                  <span className={`mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ${s.dot}`} aria-hidden="true" />
                  <div className="min-w-0 flex-1 text-sm">
                    <p className="text-stone-800">{a.description || a.name}</p>
                    {a.state === "ALARM" && <p className="text-xs text-red-700">{a.reason}</p>}
                  </div>
                  <span className={`whitespace-nowrap text-xs font-semibold ${s.text}`}>
                    {t[s.label]} · {a.since}
                  </span>
                </li>
              );
            })}
          </ul>
        </>
      )}
    </div>
  );
}
