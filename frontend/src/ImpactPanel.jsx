import { useState, useEffect } from "react";
import { api } from "./api";

const percent = (value) => (value === null ? "–" : `${value}%`);

// One headline number, with the same measure from the 4 weeks before
function Tile({ t, label, now, before }) {
  return (
    <div className="rounded-xl border border-stone-200 p-3">
      <p className="text-xs font-medium text-stone-500">{label}</p>
      <p className="mt-1 text-2xl font-bold tabular-nums text-stone-900">{now}</p>
      <p className="text-xs text-stone-500">
        {t.impactBefore}: <span className="tabular-nums">{before}</span>
      </p>
    </div>
  );
}

// GHS: SDG 3 progress. District totals only; shows activity, not proof of better health.
export default function ImpactPanel({ t }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api("/surveillance/impact")
      .then(setData)
      .catch((err) => setError(err.message));
  }, []);

  if (error) return <p className="mt-6 text-sm text-red-600">{error}</p>;
  if (!data) return null;

  const { current: now, previous: before, gap } = data;
  return (
    <div className="mt-6 rounded-2xl border border-stone-200 bg-white p-5">
      <h2 className="text-lg font-semibold text-stone-800">🎯 {t.impactTitle}</h2>
      <p className="text-xs text-stone-500">{t.impactHint}</p>
      <p className="mt-2 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800">{t.impactHonest}</p>

      <div className="mt-3 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Tile t={t} label={t.impactAntenatal} now={percent(now.antenatal.percent)} before={percent(before.antenatal.percent)} />
        <Tile t={t} label={t.impactReferrals} now={percent(now.referrals.percent)} before={percent(before.referrals.percent)} />
        <Tile t={t} label={t.impactAttended} now={percent(now.appointments.percent)} before={percent(before.appointments.percent)} />
        <Tile
          t={t}
          label={t.impactHours}
          now={now.avg_hours_to_complete ?? "–"}
          before={before.avg_hours_to_complete ?? "–"}
        />
      </div>

      {gap && (
        <p className="mt-3 text-sm text-stone-700">
          <span className="font-semibold">{t.impactGap}:</span> {gap.highest.district} {gap.highest.visits} · {gap.lowest.district}{" "}
          {gap.lowest.visits} ({t.impactDifference} {gap.difference})
          <span className="block text-xs text-stone-500">{t.impactGapHint}</span>
        </p>
      )}

      <div className="mt-3 overflow-x-auto">
        <table className="w-full text-sm" style={{ minWidth: 560 }}>
          <thead>
            <tr className="text-left text-xs text-stone-500">
              <th className="py-1 pr-2 font-medium">{t.impactDistrict}</th>
              <th className="py-1 pr-2 font-medium">{t.impactVisits}</th>
              <th className="py-1 pr-2 font-medium">{t.impactAntenatal}</th>
              <th className="py-1 pr-2 font-medium">{t.impactReferrals}</th>
              <th className="py-1 pr-2 font-medium">{t.impactAttended}</th>
            </tr>
          </thead>
          <tbody className="tabular-nums">
            {data.districts.map((d) => (
              <tr key={d.district} className="border-t border-stone-100">
                <td className="py-1.5 pr-2 font-medium text-stone-800">{d.district}</td>
                <td className="py-1.5 pr-2">{d.visits}</td>
                <td className="py-1.5 pr-2">{percent(d.antenatal.percent)}</td>
                <td className="py-1.5 pr-2">{percent(d.referrals.percent)}</td>
                <td className="py-1.5 pr-2">{percent(d.appointments.percent)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
