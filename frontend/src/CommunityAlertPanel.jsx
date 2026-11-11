import { useState, useEffect } from "react";
import { api } from "./api";
import { inputClass } from "./styles";

// Ready-made advice for each condition, so an officer can send a clear alert in seconds
const TEMPLATES = {
  cholera: "Cholera cases are rising in your area. Drink only safe water, wash hands with soap, and go to the clinic early if you have watery diarrhoea.",
  malaria: "Malaria cases are rising. Sleep under a mosquito net every night and get tested at the clinic if you have a fever.",
  meningitis: "Meningitis cases are rising. Go to the clinic at once for fever with a stiff neck or severe headache.",
  measles: "Measles cases are rising. Take children for their measles vaccine and see a health worker for fever with a rash.",
  pneumonia: "Pneumonia cases are rising. Children with fast or difficult breathing must see a health worker today.",
};

// GHS: send one health alert SMS to a district (facilities + residents who agreed)
export default function CommunityAlertPanel({ t, districts, alerts }) {
  const [district, setDistrict] = useState("");
  const [message, setMessage] = useState("");
  const [reach, setReach] = useState(null);
  const [result, setResult] = useState("");
  const [history, setHistory] = useState([]);
  const [sending, setSending] = useState(false);

  const loadHistory = () => api("/alerts/community").then(setHistory).catch(() => {});
  useEffect(() => {
    loadHistory();
  }, []);
  const chooseDistrict = (name) => {
    setDistrict(name);
    setReach(null);
    if (name) api(`/alerts/community/preview?district=${encodeURIComponent(name)}`).then(setReach).catch(() => {});
  };
  const pickAlert = (a) => {
    chooseDistrict(a.district);
    setMessage(TEMPLATES[a.condition] || "");
  };
  const send = async () => {
    setSending(true);
    try {
      const r = await api("/alerts/community", { method: "POST", body: { district, message } });
      setResult(`${t.alertSent}: ${r.delivered} / ${r.recipients} ${t.alertDelivered}`);
      setMessage("");
      loadHistory();
    } catch (err) {
      setResult(err.message);
    }
    setSending(false);
  };

  return (
    <div className="mt-6 rounded-2xl border border-stone-200 bg-white p-5">
      <h2 className="text-lg font-semibold text-stone-800">📢 {t.alertTitle}</h2>
      <p className="text-xs text-stone-500">{t.alertHint}</p>
      {alerts.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {alerts.map((a) => (
            <button key={a.district + a.condition} onClick={() => pickAlert(a)} className="rounded-full border border-red-300 bg-red-50 px-3 py-1 text-xs font-medium text-red-800 hover:bg-red-100">
              ⚠ {t["cond_" + a.condition] || a.condition} · {a.district}
            </button>
          ))}
        </div>
      )}
      <div className="mt-3 grid gap-3 sm:grid-cols-3">
        <select value={district} onChange={(e) => chooseDistrict(e.target.value)} className={inputClass}>
          <option value="">{t.alertChooseDistrict}</option>
          {districts.map((d) => (
            <option key={d.district} value={d.district}>
              {d.district}
            </option>
          ))}
        </select>
        <textarea value={message} onChange={(e) => setMessage(e.target.value)} maxLength={300} rows={3} placeholder={t.alertMessage} className={`${inputClass} sm:col-span-2`} />
      </div>
      {reach && (
        <p className="mt-2 text-xs text-stone-600">
          {t.alertReach}: {reach.facilities} {t.alertFacilities} + {reach.residents} {t.alertResidents}
        </p>
      )}
      <button
        disabled={!district || message.trim().length < 10 || sending || (reach && reach.facilities + reach.residents === 0)}
        onClick={send}
        className="mt-3 rounded-xl bg-red-700 px-4 py-2 text-sm font-semibold text-white hover:bg-red-800 disabled:opacity-50"
      >
        {sending ? t.sending : t.alertSend}
      </button>
      {result && <p className="mt-2 text-sm text-stone-700">{result}</p>}
      {history.length > 0 && (
        <ul className="mt-4 divide-y divide-stone-100 border-t border-stone-100 text-xs text-stone-600">
          {history.map((h, i) => (
            <li key={i} className="py-2">
              <span className="font-medium text-stone-800">{h.district}</span> · {h.created_at} · {h.delivered}/{h.recipients} {t.alertDelivered} · {h.sent_by}
              <span className="block text-stone-500">{h.message}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
