import { useState, useEffect } from "react";
import { api } from "./api";

// GHS: how many pharmacies in each district are out of / low on each drug.
// Counts of facilities only, never patients. A shortage of a drug for a condition the
// forecast expects in that district is flagged, so supplies can be sent first.
export default function StockOutsPanel({ t, forecasts }) {
  const [districts, setDistricts] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    api("/surveillance/stock")
      .then((data) => setDistricts(data.districts))
      .catch((err) => setError(err.message));
  }, []);

  const expected = (district, condition) =>
    forecasts.some((f) => f.district === district && f.condition === condition && f.chance >= 0.3);
  const short = districts.filter((d) => d.drugs.length > 0);

  return (
    <div className="mt-6 rounded-2xl border border-stone-200 bg-white p-5">
      <h2 className="text-lg font-semibold text-stone-800">{t.ghsStockTitle}</h2>
      <p className="text-xs text-stone-500">{t.ghsStockHint}</p>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
      {!error && short.length === 0 && <p className="mt-3 text-sm text-stone-500">✓ {t.ghsStockNone}</p>}
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        {short.map((d) => (
          <div key={d.district} className="rounded-xl border border-stone-200 p-3">
            <p className="font-semibold text-stone-900">
              {d.district} <span className="text-xs font-normal text-stone-500">· {t.pharmaciesReporting}: {d.facilities}</span>
            </p>
            <ul className="mt-2 space-y-1 text-sm">
              {d.drugs.map((drug) => (
                <li key={drug.name} className="flex items-start justify-between gap-2">
                  <span className="text-stone-700">
                    {drug.name}
                    {drug.condition && expected(d.district, drug.condition) && (
                      <span className="block text-xs font-semibold text-red-700">⚠ {t.ghsStockForecast}</span>
                    )}
                  </span>
                  <span className="whitespace-nowrap text-xs">
                    {drug.out > 0 && <span className="rounded-full bg-red-100 px-2 py-0.5 font-semibold text-red-700">{drug.out} {t.stockOutCount}</span>}{" "}
                    {drug.low > 0 && <span className="rounded-full bg-amber-100 px-2 py-0.5 font-semibold text-amber-800">{drug.low} {t.stockLowCount}</span>}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}
