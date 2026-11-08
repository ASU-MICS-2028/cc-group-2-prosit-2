import { useState, useEffect } from "react";
import { api } from "./api";
import AppShell from "./AppShell";
import TrainingPanel from "./TrainingPanel";
import { RxItems } from "./Prescriptions";
import { RX_STYLE, inputClass } from "./styles";

const STOCK_STYLE = {
  out: "bg-red-100 text-red-700",
  low: "bg-amber-100 text-amber-800",
  ok: "bg-emerald-100 text-emerald-700",
};

// Pharmacist: prescriptions and drug stock for their own facility only
export default function PharmacistApp(props) {
  const { t, user } = props;
  const [tab, setTab] = useState("prescriptions"); // prescriptions | stock | history
  const [prescriptions, setPrescriptions] = useState([]);
  const [stock, setStock] = useState([]);
  const [history, setHistory] = useState([]);
  const [error, setError] = useState("");

  // Prescriptions, stock and history all change together when a drug is dispensed
  const load = () => {
    setError("");
    api("/pharmacy/prescriptions").then(setPrescriptions).catch((err) => setError(err.message));
    api("/pharmacy/stock").then(setStock).catch((err) => setError(err.message));
    api("/pharmacy/history").then(setHistory).catch((err) => setError(err.message));
  };

  useEffect(() => {
    api("/pharmacy/prescriptions").then(setPrescriptions).catch((err) => setError(err.message));
    api("/pharmacy/stock").then(setStock).catch((err) => setError(err.message));
    api("/pharmacy/history").then(setHistory).catch((err) => setError(err.message));
  }, []);

  const waiting = prescriptions.filter((p) => p.status === "pending").length;
  const tiles = [
    ["prescriptions", t.waitingRx, waiting, "text-stone-800"],
    ["stock", t.outOfStock, stock.filter((s) => s.status === "out").length, "text-red-700"],
    ["stock", t.lowStock, stock.filter((s) => s.status === "low").length, "text-amber-700"],
  ];

  const menu = [
    { key: "prescriptions", label: t.prescriptions, icon: "pill", count: waiting },
    { key: "stock", label: t.stockTab, icon: "stock" },
    { key: "history", label: t.historyTab, icon: "history" },
    { key: "training", label: t.navTraining, icon: "training" },
  ];

  return (
    <AppShell {...props} items={menu} active={tab} onSelect={setTab}>
        {tab !== "training" && (<>
        <h1 className="text-2xl font-bold text-stone-800">{t.pharmacyTitle}</h1>
        <p className="mt-1 text-sm text-stone-500">
          {t.pharmacyHint} <span className="font-medium text-stone-700">{user.facility}</span>
        </p>

        <div className="mt-5 grid grid-cols-3 gap-3">
          {tiles.map(([target, label, n, colour]) => (
            <button key={label} onClick={() => setTab(target)} className="rounded-2xl border border-stone-200 bg-white p-4 text-left hover:border-teal-300">
              <p className="text-xs font-medium text-stone-500">{label}</p>
              <p className={`mt-1 text-3xl font-bold ${colour}`}>{n}</p>
            </button>
          ))}
        </div>
        </>)}

        {error && <p className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

        {tab === "prescriptions" && (
          <div className="mt-4 space-y-3">
            {prescriptions.length === 0 && (
              <div className="rounded-2xl border border-dashed border-stone-300 bg-white p-10 text-center text-sm text-stone-500">{t.noPrescriptions}</div>
            )}
            {prescriptions.map((rx) => (
              <PrescriptionCard key={rx.id} rx={rx} t={t} onDone={load} />
            ))}
          </div>
        )}
        {tab === "stock" && (
          <div className="mt-4 space-y-2">
            {stock.map((s) => (
              <StockRow key={s.drug_id} s={s} t={t} onChanged={load} />
            ))}
          </div>
        )}
        {tab === "history" && <StockHistory history={history} t={t} />}

        {tab === "training" && <TrainingPanel t={t} role={user.role} userId={user.id} />}
    </AppShell>
  );
}

function PrescriptionCard({ rx, t, onDone }) {
  const [error, setError] = useState("");
  const dispense = async () => {
    setError("");
    try {
      await api(`/pharmacy/prescriptions/${rx.id}/dispense`, { method: "POST" });
      onDone();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className={`rounded-2xl border bg-white p-5 ${rx.status === "pending" ? "border-amber-300" : "border-stone-200"}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          {/* Enough to hand the drugs to the right person; no visit history (need-to-know) */}
          <p className="text-lg font-semibold text-stone-800">{rx.full_name}</p>
          <p className="text-sm text-stone-500">
            <span className="font-mono">{rx.ref}</span> · {t[rx.sex] || ""} · {t.age} {rx.age}
          </p>
        </div>
        <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${RX_STYLE[rx.status]}`}>{t["rx_" + rx.status]}</span>
      </div>
      <RxItems rx={rx} t={t} showStock />
      {rx.notes && <p className="mt-2 rounded-xl bg-amber-50 px-3 py-2 text-sm text-amber-900">{rx.notes}</p>}
      <p className="mt-2 text-xs text-stone-500">
        {t.prescribedBy} {rx.prescribed_by_name} · {rx.created_at}
        {rx.dispensed_at && ` · ${t.dispensedBy} ${rx.dispensed_by_name} · ${rx.dispensed_at}`}
      </p>
      {error && <p className="mt-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      {rx.status === "pending" && (
        <button onClick={dispense} className="mt-3 rounded-xl bg-teal-700 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-800">
          {t.dispense}
        </button>
      )}
    </div>
  );
}

function StockRow({ s, t, onChanged }) {
  const [mode, setMode] = useState(null); // null | "receive" | "adjust" | "reorder"
  const [amount, setAmount] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState("");

  const open = (m) => {
    setMode(mode === m ? null : m);
    setAmount(m === "reorder" ? String(s.reorder_level) : "");
    setNote("");
    setError("");
  };

  const save = async () => {
    const paths = {
      receive: [`/pharmacy/stock/${s.drug_id}/receive`, { quantity: Number(amount), note }],
      adjust: [`/pharmacy/stock/${s.drug_id}/adjust`, { new_quantity: Number(amount), note }],
      reorder: [`/pharmacy/stock/${s.drug_id}/reorder-level`, { reorder_level: Number(amount) }],
    };
    const [path, body] = paths[mode];
    try {
      await api(path, { method: "POST", body });
      setMode(null);
      onChanged();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="rounded-xl border border-stone-200 bg-white p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="font-medium text-stone-800">{s.name}</p>
          <p className="text-xs text-stone-500">
            {t.reorderAt} {s.reorder_level} {s.unit}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-lg font-bold tabular-nums text-stone-800">
            {s.quantity} <span className="text-xs font-normal text-stone-500">{s.unit}</span>
          </span>
          <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${STOCK_STYLE[s.status]}`}>{t["stock_" + s.status]}</span>
        </div>
      </div>
      <div className="mt-2 flex gap-3 text-sm">
        <button onClick={() => open("receive")} className="font-medium text-teal-700 hover:underline">+ {t.receive}</button>
        <button onClick={() => open("adjust")} className="font-medium text-stone-600 hover:underline">{t.adjust}</button>
        <button onClick={() => open("reorder")} className="font-medium text-stone-600 hover:underline">{t.reorderAt}</button>
      </div>
      {mode && (
        <div className="mt-2 flex flex-wrap gap-2 rounded-lg bg-stone-50 p-2">
          <input
            type="number"
            min="0"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder={mode === "adjust" ? t.newCount : t.quantity}
            className={`${inputClass} w-32`}
          />
          {mode !== "reorder" && (
            <input
              value={note}
              onChange={(e) => setNote(e.target.value)}
              maxLength={200}
              placeholder={mode === "adjust" ? t.adjustNote : t.receivedNote}
              className={`${inputClass} flex-1`}
            />
          )}
          <button
            onClick={save}
            disabled={amount === "" || (mode === "adjust" && note.trim().length < 3)}
            className="rounded-xl bg-teal-700 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-800 disabled:opacity-50"
          >
            {t.saveChanges}
          </button>
          {error && <p className="w-full text-sm text-red-600">{error}</p>}
        </div>
      )}
    </div>
  );
}

function StockHistory({ history, t }) {
  if (history.length === 0) {
    return <p className="mt-4 text-sm text-stone-500">{t.noStockHistory}</p>;
  }
  return (
    <div className="mt-4 overflow-x-auto rounded-2xl border border-stone-200 bg-white">
      <table className="w-full text-sm">
        <tbody className="divide-y divide-stone-100">
          {history.map((h) => (
            <tr key={h.id}>
              <td className="whitespace-nowrap px-3 py-2 text-xs text-stone-500">{h.created_at}</td>
              <td className="px-3 py-2">
                <p className="font-medium text-stone-800">{h.name}</p>
                <p className="text-xs text-stone-500">
                  {t["move_" + h.reason]} · {t.by} {h.by_name}
                  {h.note && ` · ${h.note}`}
                  {h.prescription_id && ` · Rx ${h.prescription_id}`}
                </p>
              </td>
              <td className={`whitespace-nowrap px-3 py-2 text-right font-semibold tabular-nums ${h.change < 0 ? "text-red-700" : "text-emerald-700"}`}>
                {h.change > 0 ? `+${h.change}` : h.change}
              </td>
              <td className="whitespace-nowrap px-3 py-2 text-right tabular-nums text-stone-600">= {h.quantity_after}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
