import { useState, useEffect } from "react";
import { api } from "./api";
import { inputClass } from "./styles";

const CODES = ["bed_nets", "safe_water", "latrine", "long_cough", "child_no_net", "diarrhoea"];
const GOOD_IF_YES = { bed_nets: true, safe_water: true, latrine: true, long_cough: false, child_no_net: false, diarrhoea: false };

// CHV home: a 6-question household survey. No names are asked.
export default function SurveyPanel({ t }) {
  const [open, setOpen] = useState(false);
  const [community, setCommunity] = useState("");
  const [people, setPeople] = useState("");
  const [answers, setAnswers] = useState({});
  const [done, setDone] = useState(null);
  const [message, setMessage] = useState("");

  const loadCount = () => api("/chv/surveys").then((d) => setDone(d.last_30_days)).catch(() => {});
  useEffect(() => {
    loadCount();
  }, []);

  const complete = people && CODES.every((c) => c in answers);
  const submit = async (e) => {
    e.preventDefault();
    try {
      await api("/surveys", { method: "POST", body: { community, people: Number(people), answers } });
      setAnswers({});
      setPeople("");
      setMessage(t.surveySaved);
      loadCount();
    } catch (err) {
      setMessage(err.message);
    }
  };

  return (
    <div className="mt-5 rounded-2xl border border-stone-200 bg-white p-4">
      <button onClick={() => setOpen(!open)} className="w-full text-left font-semibold text-stone-800">
        {open ? "▾" : "▸"} 📋 {t.surveyTitle}
        {done !== null && <span className="ml-2 text-xs font-normal text-stone-500">{t.surveyCount}: {done}</span>}
      </button>
      {open && (
        <form onSubmit={submit} className="mt-3 space-y-3">
          <p className="text-xs text-stone-500">{t.surveyHint}</p>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-stone-600">{t.community}</label>
              <input value={community} onChange={(e) => setCommunity(e.target.value)} className={inputClass} />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-stone-600">{t.surveyPeople}</label>
              <input type="number" min="1" max="50" value={people} onChange={(e) => setPeople(e.target.value)} className={inputClass} />
            </div>
          </div>
          {CODES.map((code) => (
            <div key={code} className="flex items-center justify-between gap-3 border-t border-stone-100 pt-2">
              <span className="text-sm text-stone-700">{t["survey_" + code]}</span>
              <div className="flex shrink-0 gap-1">
                {[true, false].map((value) => (
                  <button
                    key={String(value)}
                    type="button"
                    onClick={() => setAnswers({ ...answers, [code]: value })}
                    className={`rounded-full border px-3 py-1 text-sm ${
                      answers[code] === value
                        ? value === GOOD_IF_YES[code]
                          ? "border-emerald-600 bg-emerald-600 text-white"
                          : "border-red-600 bg-red-600 text-white"
                        : "border-stone-300 text-stone-700"
                    }`}
                  >
                    {value ? t.yes : t.no}
                  </button>
                ))}
              </div>
            </div>
          ))}
          <button disabled={!complete} className="w-full rounded-xl bg-teal-700 py-2.5 text-sm font-semibold text-white disabled:opacity-50">
            {t.surveySubmit}
          </button>
          {message && <p className="text-sm text-teal-800">{message}</p>}
        </form>
      )}
    </div>
  );
}

// GHS: share of surveyed households per district answering "yes" (last 90 days)
export function SurveyResultsPanel({ t }) {
  const [data, setData] = useState(null);
  useEffect(() => {
    api("/surveillance/surveys").then(setData).catch(() => {});
  }, []);
  if (!data || data.districts.length === 0) return null;
  const cell = (code, pct) => {
    if (pct === null) return <span className="text-stone-400">{t.immTooFew}</span>;
    const bad = GOOD_IF_YES[code] ? pct < 50 : pct >= 20;
    return <span className={bad ? "font-semibold text-red-700" : "text-stone-800"}>{pct}%</span>;
  };
  return (
    <div className="mt-6 overflow-x-auto rounded-2xl border border-stone-200 bg-white p-5">
      <h2 className="text-lg font-semibold text-stone-800">📋 {t.surveyResultsTitle}</h2>
      <p className="text-xs text-stone-500">{t.surveyResultsHint}</p>
      <table className="mt-3 w-full text-sm">
        <thead>
          <tr className="text-left text-xs text-stone-500">
            <th className="py-1 pr-2">{t.immDistrict}</th>
            <th className="pr-2">{t.surveyHouseholds}</th>
            {CODES.map((c) => (
              <th key={c} className="pr-2">{t["surveyShort_" + c]}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-stone-100">
          {data.districts.map((d) => (
            <tr key={d.district}>
              <td className="py-2 pr-2 font-medium text-stone-800">{d.district}</td>
              <td className="pr-2">{d.households}</td>
              {CODES.map((c) => (
                <td key={c} className="pr-2">{cell(c, d.yes_pct[c])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
