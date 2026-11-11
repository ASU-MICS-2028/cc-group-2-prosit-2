import { useState, useEffect } from "react";
import { api } from "./api";
import { inputClass } from "./styles";

const STATUS_STYLE = {
  given: "bg-emerald-100 text-emerald-800",
  overdue: "bg-red-100 text-red-700",
  due: "bg-amber-100 text-amber-800",
  upcoming: "bg-stone-100 text-stone-500",
};
const todayText = () => new Date().toISOString().slice(0, 10);

// CHV patient page, children under 5: the vaccination card (Ghana EPI schedule)
export default function ImmunisationPanel({ t, patientId }) {
  const [data, setData] = useState(null);
  const [birthDate, setBirthDate] = useState("");
  const [recording, setRecording] = useState(null); // dose code being recorded
  const [givenOn, setGivenOn] = useState(todayText());
  const [error, setError] = useState("");

  const load = () => api(`/patients/${patientId}/immunisations`).then(setData).catch((err) => setError(err.message));
  useEffect(() => {
    load();
  }, [patientId]); // eslint-disable-line react-hooks/exhaustive-deps

  const run = async (path, options) => {
    try {
      setError("");
      await api(path, options);
      setRecording(null);
      load();
    } catch (err) {
      setError(err.message);
    }
  };

  if (!data) return null;
  const counts = (status) => data.schedule.filter((d) => d.status === status).length;

  return (
    <div className="mt-4 rounded-2xl border border-stone-200 bg-white p-4">
      <h2 className="font-semibold text-stone-800">💉 {t.immTitle}</h2>
      {!data.birth_date ? (
        <div className="mt-2">
          <p className="text-sm text-stone-600">{t.immNeedBirthDate}</p>
          <div className="mt-2 flex gap-2">
            <input type="date" max={todayText()} value={birthDate} onChange={(e) => setBirthDate(e.target.value)} className={inputClass} />
            <button
              disabled={!birthDate}
              onClick={() => run(`/patients/${patientId}/birth-date`, { method: "POST", body: { birth_date: birthDate } })}
              className="rounded-xl bg-teal-700 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-800 disabled:opacity-50"
            >
              {t.saveChanges}
            </button>
          </div>
        </div>
      ) : (
        <>
          <p className="text-xs text-stone-500">
            {t.immBorn} {data.birth_date} · ✅ {counts("given")} · <span className="text-red-700">{t.imm_overdue} {counts("overdue")}</span> ·{" "}
            <span className="text-amber-800">{t.imm_due} {counts("due")}</span>
          </p>
          <ul className="mt-2 divide-y divide-stone-100">
            {data.schedule.map((d) => (
              <li key={d.code} className="py-2 text-sm">
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <span className="font-medium text-stone-800">{d.name}</span>
                    <span className="block text-xs text-stone-500">
                      {d.status === "given" ? `${t.immGivenOn} ${d.given_on}` : `${t.immDueOn} ${d.due_on}`} · {d.protects}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${STATUS_STYLE[d.status]}`}>{t["imm_" + d.status]}</span>
                    {d.status === "given" ? (
                      <button onClick={() => run(`/patients/${patientId}/immunisations/${d.code}`, { method: "DELETE" })} className="text-xs text-stone-400 hover:text-red-600">
                        {t.immUndo}
                      </button>
                    ) : (
                      d.status !== "upcoming" && (
                        <button onClick={() => { setRecording(d.code); setGivenOn(todayText()); }} className="text-xs font-semibold text-teal-700 hover:underline">
                          {t.immRecord}
                        </button>
                      )
                    )}
                  </div>
                </div>
                {recording === d.code && (
                  <div className="mt-2 flex items-center gap-2 rounded-xl bg-teal-50 p-2">
                    <span className="text-xs text-stone-600">{t.immGivenOn}</span>
                    <input type="date" min={data.birth_date} max={todayText()} value={givenOn} onChange={(e) => setGivenOn(e.target.value)} className={inputClass} />
                    <button
                      onClick={() => run(`/patients/${patientId}/immunisations`, { method: "POST", body: { vaccine: d.code, given_on: givenOn } })}
                      className="rounded-xl bg-teal-700 px-3 py-2 text-xs font-semibold text-white"
                    >
                      {t.saveChanges}
                    </button>
                  </div>
                )}
              </li>
            ))}
          </ul>
          <p className="mt-2 text-xs text-stone-400">{t.immSource}</p>
        </>
      )}
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
    </div>
  );
}

// CHV home: children with a vaccine overdue or due in the next 2 weeks
export function VaccinesDueList({ t, onOpen }) {
  const [items, setItems] = useState([]);
  useEffect(() => {
    api("/chv/immunisations-due").then(setItems).catch(() => {}); // no signal: simply not shown
  }, []);
  if (items.length === 0) return null;
  return (
    <div className="mt-5 rounded-2xl border border-sky-200 bg-sky-50 p-4">
      <h2 className="font-semibold text-sky-900">💉 {t.immDueList} ({items.length})</h2>
      <ul className="mt-2 divide-y divide-sky-200">
        {items.map((c) => (
          <li key={c.patient_id}>
            <button onClick={() => onOpen(c.patient_id)} className="w-full py-2 text-left text-sm hover:underline">
              <span className="font-medium text-stone-800">{c.full_name}</span> <span className="font-mono text-xs text-stone-500">{c.ref}</span>
              {c.community && <span className="text-stone-600"> · {c.community}</span>}
              <span className="block text-xs text-stone-600">
                {c.overdue > 0 && <span className="font-semibold text-red-700">{t.imm_overdue} {c.overdue} · </span>}
                {c.doses.join(", ")}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

// GHS: share of children under 5 who are up to date, per district (totals only)
export function ImmunisationCoveragePanel({ t }) {
  const [rows, setRows] = useState([]);
  useEffect(() => {
    api("/surveillance/immunisation").then(setRows).catch(() => {});
  }, []);
  if (rows.length === 0) return null;
  const pct = (v) => (v === null ? <span className="text-stone-400">{t.immTooFew}</span> : `${v}%`);
  return (
    <div className="mt-6 rounded-2xl border border-stone-200 bg-white p-5">
      <h2 className="text-lg font-semibold text-stone-800">💉 {t.immCoverageTitle}</h2>
      <p className="text-xs text-stone-500">{t.immCoverageHint}</p>
      <table className="mt-3 w-full text-sm">
        <thead>
          <tr className="text-left text-xs text-stone-500">
            <th className="py-1">{t.immDistrict}</th>
            <th>{t.immTracked}</th>
            <th>{t.immUpToDate}</th>
            <th>{t.immMeasles}</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-stone-100">
          {rows.map((r) => (
            <tr key={r.district}>
              <td className="py-2 font-medium text-stone-800">{r.district}</td>
              <td>{r.tracked}</td>
              <td className={r.up_to_date_pct !== null && r.up_to_date_pct < 70 ? "font-semibold text-red-700" : ""}>{pct(r.up_to_date_pct)}</td>
              <td>{pct(r.measles_pct)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
