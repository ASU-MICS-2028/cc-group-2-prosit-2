import { useState, useEffect } from "react";
import { api } from "./api";

const KIND_STYLE = {
  controlled: "bg-purple-100 text-purple-800",
  duplicate: "bg-amber-100 text-amber-800",
  high_volume: "bg-red-100 text-red-700",
  code_guessing: "bg-red-100 text-red-700",
};

// GHS: fraud and safety warnings about prescriptions (doctors and facilities, no patients)
export default function PrescriptionFlagsPanel({ t }) {
  const [flags, setFlags] = useState([]);
  useEffect(() => {
    api("/surveillance/prescription-flags").then(setFlags).catch(() => {});
  }, []);
  if (flags.length === 0) return null;
  return (
    <div className="mt-6 rounded-2xl border border-stone-200 bg-white p-5">
      <h2 className="text-lg font-semibold text-stone-800">💊 {t.rxFlagsTitle} ({flags.length})</h2>
      <p className="text-xs text-stone-500">{t.rxFlagsHint}</p>
      <ul className="mt-3 divide-y divide-stone-100">
        {flags.map((f) => (
          <li key={f.id} className="py-2 text-sm">
            <span className={`mr-2 rounded-full px-2 py-0.5 text-xs font-semibold ${KIND_STYLE[f.kind] || "bg-stone-100"}`}>{t["rxFlag_" + f.kind] || f.kind}</span>
            <span className="text-stone-800">{f.detail}</span>
            <span className="block text-xs text-stone-500">
              {f.created_at.slice(0, 16)}
              {f.doctor && ` · ${f.doctor}, ${f.facility}`}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
