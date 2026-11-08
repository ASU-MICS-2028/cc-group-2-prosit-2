import { useState, useEffect, useCallback } from "react";
import { api } from "./api";
import StockOutsPanel from "./StockOutsPanel";
import ImpactPanel from "./ImpactPanel";
import Header from "./Header";
import DistrictMap from "./DistrictMap";

const CONDITIONS = ["malaria", "cholera", "meningitis", "measles", "pneumonia", "hypertension"];

// Sequential blue ramp (one hue, light -> dark = fewer -> more cases)
function heatStyle(value) {
  if (value === 0) return { background: "#fcfcfb", color: "#898781" };
  if (value === "<5") return { background: "#cde2fb", color: "#0b0b0b" };
  if (value < 10) return { background: "#86b6ef", color: "#0b0b0b" };
  if (value < 20) return { background: "#2a78d6", color: "#ffffff" };
  return { background: "#184f95", color: "#ffffff" };
}

// GHS officer: anonymised district totals and outbreak alerts. Never names.
export default function GhsApp(props) {
  const { t } = props;
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState(null); // { district, condition } shown in the trend chart
  const [hover, setHover] = useState(null); // text for the hover readout under the heatmap
  const selectFromMap = useCallback((sel) => setSelected(sel), []);

  useEffect(() => {
    api("/surveillance/summary?weeks=8")
      .then((d) => {
        setData(d);
        // Open the trend on the biggest alert, or the first district
        const a = d.alerts[0];
        if (a) setSelected({ district: a.district, condition: a.condition });
        else if (d.districts[0]) setSelected({ district: d.districts[0].district, condition: "malaria" });
      })
      .catch((err) => setError(err.message));
  }, []);

  // Download last week's totals in DHIS2 format (simulated: nothing is sent to DHIMS2)
  const exportDhims2 = async () => {
    try {
      const file = await api("/surveillance/dhims2-export");
      const blob = new Blob([JSON.stringify(file, null, 2)], { type: "application/json" });
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = `dhims2-${file.period}.json`;
      link.click();
      URL.revokeObjectURL(link.href);
    } catch (err) {
      setError(err.message);
    }
  };

  if (error) return <p className="p-6 text-red-600">{error}</p>;
  if (!data) return null;

  const tiles = [
    [t.ghsVisits, data.totals_this_week.visits],
    [t.ghsHighRisk, data.totals_this_week.high_risk],
    [t.ghsReferrals, data.totals_this_week.referrals],
    [t.ghsAlerts, data.totals_this_week.alerts],
  ];
  const selectedRow = selected && data.districts.find((d) => d.district === selected.district);

  return (
    <div className="min-h-screen bg-stone-50">
      <Header {...props} />
      <main className="mx-auto max-w-5xl px-4 py-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <h1 className="text-2xl font-bold text-stone-800">{t.ghsTitle}</h1>
          <div className="text-right">
            <button
              onClick={exportDhims2}
              className="rounded-xl border border-stone-300 bg-white px-3 py-2 text-sm font-medium text-stone-700 hover:bg-stone-100"
            >
              ⬇ {t.ghsExport}
            </button>
            <p className="mt-1 text-[11px] text-stone-400">{t.ghsExportNote}</p>
          </div>
        </div>
        <p className="mt-1 text-sm text-stone-500">{t.ghsHint}</p>
        <p className="mt-1 text-xs text-stone-400">
          {t.ghsPrivacy} · {t.ghsUpdated} {data.generated_at}
        </p>

        {/* KPI row: last 7 days */}
        <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {tiles.map(([label, value]) => (
            <div key={label} className="rounded-2xl border border-stone-200 bg-white p-4">
              <p className="text-xs font-medium text-stone-500">{label}</p>
              <p className="mt-1 text-3xl font-bold tabular-nums text-stone-900">{value}</p>
            </div>
          ))}
        </div>

        {/* Outbreak alerts: critical status = icon + label + colour */}
        <div className="mt-5 space-y-2">
          {data.alerts.length === 0 && <p className="text-sm text-stone-500">✓ {t.ghsNoAlerts}</p>}
          {data.alerts.map((a) => (
            <button
              key={a.district + a.condition}
              onClick={() => setSelected({ district: a.district, condition: a.condition })}
              className="flex w-full items-center gap-3 rounded-2xl border-l-4 bg-white p-4 text-left shadow-sm hover:shadow-md"
              style={{ borderLeftColor: "#d03b3b" }}
            >
              <span className="text-xl" aria-hidden="true">⚠</span>
              <div>
                <p className="text-xs font-bold uppercase tracking-wide" style={{ color: "#d03b3b" }}>
                  {t.ghsAlertLabel}
                </p>
                <p className="font-semibold text-stone-900">
                  {t["cond_" + a.condition]} · {a.district}
                </p>
                <p className="text-sm text-stone-600">
                  <span className="font-semibold tabular-nums text-stone-900">{a.this_week}</span> {t.ghsThisWeek} ·{" "}
                  {t.ghsUsual} ~{a.usual}
                </p>
              </div>
            </button>
          ))}
        </div>

        <ForecastPanel t={t} forecasts={data.forecasts} onSelect={setSelected} />

        <StockOutsPanel t={t} forecasts={data.forecasts} />

        <ImpactPanel t={t} />

        <DistrictMap t={t} districts={data.districts} alerts={data.alerts} conditions={CONDITIONS} onSelect={selectFromMap} />

        {/* Heatmap table: districts x conditions, last 7 days */}
        <div className="mt-6 rounded-2xl border border-stone-200 bg-white p-5">
          <h2 className="text-lg font-semibold text-stone-800">{t.ghsHeatTitle}</h2>
          <p className="text-xs text-stone-500">{t.ghsHeatHint}</p>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full table-fixed border-separate text-sm" style={{ borderSpacing: 2, minWidth: 640 }}>
              <colgroup>
                <col style={{ width: "26%" }} />
                <col style={{ width: "8%" }} />
                {CONDITIONS.map((c) => (
                  <col key={c} />
                ))}
              </colgroup>
              <thead>
                <tr>
                  <th className="px-2 py-1 text-left text-xs font-medium text-stone-500">{t.ghsDistrict}</th>
                  <th className="px-2 py-1 text-right text-xs font-medium text-stone-500">{t.ghsVisitsShort}</th>
                  {CONDITIONS.map((c) => (
                    <th key={c} className="px-2 py-1 text-center text-xs font-medium text-stone-500">
                      {t["short_" + c]}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.districts.map((d) => (
                  <tr key={d.district}>
                    <td className="whitespace-nowrap px-2 py-1 font-medium text-stone-800">{d.district}</td>
                    <td className="px-2 py-1 text-right tabular-nums text-stone-600">{d.visits_this_week}</td>
                    {CONDITIONS.map((c) => {
                      const value = d.conditions[c][0];
                      const isSel = selected?.district === d.district && selected?.condition === c;
                      const label = `${d.district} · ${t["cond_" + c]} · ${value} ${t.ghsThisWeek}`;
                      return (
                        <td key={c} className="p-0">
                          <button
                            onClick={() => setSelected({ district: d.district, condition: c })}
                            onMouseEnter={() => setHover(label)}
                            onFocus={() => setHover(label)}
                            onMouseLeave={() => setHover(null)}
                            aria-label={label}
                            className={`h-9 w-full rounded font-semibold tabular-nums transition hover:brightness-110 ${
                              isSel ? "outline outline-2 outline-offset-1 outline-stone-900" : ""
                            }`}
                            style={heatStyle(value)}
                          >
                            {value}
                          </button>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-2 h-5 text-xs text-stone-600">{hover || t.ghsHoverHint}</p>
        </div>

        {/* Trend: one district + condition over 8 weeks */}
        {selectedRow && (
          <TrendChart
            t={t}
            district={selected.district}
            condition={selected.condition}
            series={selectedRow.conditions[selected.condition]}
            alertUsual={data.alerts.find((a) => a.district === selected.district && a.condition === selected.condition)?.usual}
          />
        )}

        <p className="mt-12 text-center text-xs text-stone-400">{t.builtBy}</p>
      </main>
    </div>
  );
}

// Column chart, emphasis style: this week in blue, earlier weeks in grey.
// A dashed line marks the "usual" level (average of the 4 weeks before this one).
function TrendChart({ t, district, condition, series, alertUsual }) {
  const [hover, setHover] = useState(null);
  const weeks = [...series].reverse(); // oldest -> newest, left to right
  const numeric = (v) => (typeof v === "number" ? v : 0); // "<5" is hidden, drawn as a stub
  const max = Math.max(5, ...weeks.map(numeric));
  const known = series.slice(1, 5).filter((v) => typeof v === "number");
  // Usual level: from the server's alert if there is one (it knows the hidden "<5" values),
  // otherwise only when all 4 earlier weeks are visible numbers
  const usual = alertUsual ?? (known.length === 4 ? known.reduce((a, b) => a + b, 0) / 4 : null);
  const H = 160; // plot height in px

  return (
    <div className="mt-6 rounded-2xl border border-stone-200 bg-white p-5">
      <h2 className="text-lg font-semibold text-stone-800">
        {t["cond_" + condition]} · {district}
      </h2>
      <p className="text-xs text-stone-500">{t.ghsTrendHint}</p>

      <div className="relative mt-6" style={{ height: H }}>
        {/* usual level (dashed line) */}
        {usual !== null && usual > 0 && (
          <div className="absolute inset-x-0 border-t border-dashed" style={{ bottom: (usual / max) * H, borderColor: "#898781" }}>
            <span className="absolute -top-4 left-0 text-[10px] text-stone-500">
              {t.ghsUsual} ~{usual.toFixed(1)}
            </span>
          </div>
        )}
        <div className="absolute inset-0 flex items-end justify-around border-b" style={{ borderColor: "#c3c2b7" }}>
          {weeks.map((v, i) => {
            const isNow = i === weeks.length - 1;
            const weeksAgo = weeks.length - 1 - i;
            const label = `${isNow ? t.ghsWeekNow : `${weeksAgo} ${t.ghsWeeksAgo}`}: ${v}`;
            return (
              <button
                key={i}
                onMouseEnter={() => setHover(label)}
                onFocus={() => setHover(label)}
                onMouseLeave={() => setHover(null)}
                aria-label={label}
                className="flex h-full w-10 flex-col items-center justify-end"
              >
                <span className="mb-1 text-xs font-semibold tabular-nums text-stone-700">{v}</span>
                <span
                  className="block w-6 rounded-t transition hover:brightness-110"
                  style={{
                    height: v === "<5" ? 3 : Math.max(numeric(v) ? 3 : 0, (numeric(v) / max) * (H - 24)),
                    background: isNow ? "#2a78d6" : "#c3c2b7",
                  }}
                />
              </button>
            );
          })}
        </div>
      </div>
      <div className="mt-1 flex justify-around text-[10px] text-stone-500">
        {weeks.map((_, i) => (
          <span key={i} className="w-10 text-center">
            {i === weeks.length - 1 ? t.ghsWeekNow : `-${weeks.length - 1 - i}w`}
          </span>
        ))}
      </div>
      <p className="mt-2 h-5 text-xs text-stone-600">{hover || t.ghsHoverColumn}</p>
    </div>
  );
}

// Outlook colours from the status palette, always with an icon + text label (never colour alone)
const OUTLOOK = {
  high: { color: "#ec835a", icon: "▲" }, // serious
  possible: { color: "#fab219", icon: "△" }, // warning
};
const ARROW = { rising: "↗", steady: "→", falling: "↘" };

// Next 2 weeks: chance of an outbreak per district and disease (backend/forecast.py, statistics, not ML)
function ForecastPanel({ t, forecasts, onSelect }) {
  const shown = forecasts.filter((f) => f.chance >= 0.3);
  const percent = (chance) => (chance >= 0.99 ? ">99%" : `${Math.round(chance * 100)}%`);

  return (
    <div className="mt-6 rounded-2xl border border-stone-200 bg-white p-5">
      <h2 className="text-lg font-semibold text-stone-800">{t.ghsForecastTitle}</h2>
      <p className="text-xs text-stone-500">{t.ghsForecastHint}</p>
      <div className="mt-3 space-y-2">
        {shown.length === 0 && <p className="text-sm text-stone-500">✓ {t.ghsForecastNone}</p>}
        {shown.map((f) => {
          const level = f.chance >= 0.6 ? "high" : "possible";
          const expected = f.expected_next_2_weeks;
          return (
            <button
              key={f.district + f.condition}
              onClick={() => onSelect({ district: f.district, condition: f.condition })}
              className="flex w-full items-start gap-3 rounded-xl border border-l-4 border-stone-200 p-3 text-left hover:shadow-md"
              style={{ borderLeftColor: OUTLOOK[level].color }}
            >
              <span className="text-lg" style={{ color: OUTLOOK[level].color }} aria-hidden="true">
                {OUTLOOK[level].icon}
              </span>
              <div className="text-sm">
                <p className="text-xs font-bold uppercase tracking-wide text-stone-700">
                  {level === "high" ? t.ghsForecastHigh : t.ghsForecastPossible} · {percent(f.chance)}
                </p>
                <p className="font-semibold text-stone-900">
                  {t["cond_" + f.condition]} · {f.district}
                </p>
                <p className="text-stone-600">
                  {t.ghsForecastExpected} <span className="font-semibold tabular-nums text-stone-900">{expected}</span>{" "}
                  ({ARROW[f.direction]} {t["trend_" + f.direction]}) · {t.ghsForecastLevel} {f.outbreak_level} {t.ghsPerWeek}
                </p>
                <p className="text-stone-600">
                  {t.ghsForecastPrepare} {expected === "<5" ? t.ghsForecastAFew : `~${expected}`} {t["supply_" + f.condition]}
                </p>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
