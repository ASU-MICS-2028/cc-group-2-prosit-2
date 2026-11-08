import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

const GHANA = [[4.6, -3.4], [11.2, 1.3]]; // map view: all of Ghana
const BLUE = "#2a78d6";
const CRITICAL = "#d03b3b";
const SIZE = 5; // bubble radius = SIZE * sqrt(cases): AREA grows with cases, not width

function radius(value) {
  if (value === 0) return 3;
  if (value === "<5") return SIZE * Math.sqrt(2.5); // hidden small count: mid-size, dashed outline
  return SIZE * Math.sqrt(value);
}

// Bubble map of the last 7 days: one bubble per district centre (never patient locations)
export default function DistrictMap({ t, districts, alerts, conditions, onSelect }) {
  const box = useRef(null);
  const mapRef = useRef(null);
  const layerRef = useRef(null);
  const [measure, setMeasure] = useState("high_risk");

  // Create the map once
  useEffect(() => {
    // zoomSnap 0.25: allow in-between zoom levels so Ghana fills the box
    const map = L.map(box.current, { scrollWheelZoom: false, zoomSnap: 0.25 }).fitBounds(GHANA, { padding: [8, 8] });
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 12,
      attribution: "© OpenStreetMap contributors",
    }).addTo(map);
    layerRef.current = L.layerGroup().addTo(map);
    mapRef.current = map;
    return () => map.remove();
  }, []);

  // Redraw bubbles whenever the data or the chosen measure changes
  useEffect(() => {
    const layer = layerRef.current;
    layer.clearLayers();
    for (const d of districts) {
      if (!d.centre) continue;
      const value = measure === "high_risk" ? d.high_risk_this_week : d.conditions[measure][0];
      const alerted = alerts.some((a) => a.district === d.district && (measure === "high_risk" || a.condition === measure));
      const circle = L.circleMarker(d.centre, {
        radius: radius(value),
        color: alerted ? CRITICAL : "#ffffff", // 2px surface ring, red if alert
        weight: alerted ? 3 : 2,
        dashArray: value === "<5" ? "3 3" : null,
        fillColor: value === 0 ? "#c3c2b7" : BLUE,
        fillOpacity: 0.7,
      }).addTo(layer);

      // Tooltip text set with textContent (never build HTML from data)
      const tip = document.createElement("div");
      const strong = document.createElement("strong");
      strong.textContent = `${value}`;
      tip.append(strong, ` ${measure === "high_risk" ? t.ghsHighRisk : t["short_" + measure]} · ${d.district}`);
      circle.bindTooltip(tip, { direction: "top" });
      if (alerted) {
        const label = document.createElement("span");
        label.textContent = `⚠ ${t.ghsAlertLabel}`;
        L.tooltip({ permanent: true, direction: "right", offset: [radius(value) + 2, 0], className: "hc-alert-label" })
          .setLatLng(d.centre)
          .setContent(label)
          .addTo(layer);
      }
      if (measure !== "high_risk") circle.on("click", () => onSelect({ district: d.district, condition: measure }));
    }
  }, [districts, alerts, measure, t, onSelect]);

  return (
    <div className="mt-6 rounded-2xl border border-stone-200 bg-white p-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-stone-800">{t.ghsMapTitle}</h2>
          <p className="text-xs text-stone-500">{t.ghsMapHint}</p>
        </div>
        <select
          value={measure}
          onChange={(e) => setMeasure(e.target.value)}
          className="rounded-xl border border-stone-300 bg-white px-3 py-2 text-sm"
          aria-label={t.ghsMapMeasure}
        >
          <option value="high_risk">{t.ghsHighRisk}</option>
          {conditions.map((c) => (
            <option key={c} value={c}>
              {t["short_" + c]}
            </option>
          ))}
        </select>
      </div>

      <div ref={box} className="relative z-0 mt-3 h-[420px] overflow-hidden rounded-xl" />

      {/* Legend: bubble size and alert ring */}
      <div className="mt-3 flex flex-wrap items-center gap-4 text-xs text-stone-600">
        {[5, 10, 20].map((n) => (
          <span key={n} className="flex items-center gap-1.5">
            <span
              className="inline-block rounded-full border-2 border-white"
              style={{ width: radius(n) * 2, height: radius(n) * 2, background: BLUE, opacity: 0.7 }}
            />
            {n}
          </span>
        ))}
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-3 w-3 rounded-full border border-dashed border-stone-500" style={{ background: BLUE, opacity: 0.7 }} />
          {t.ghsMapHidden}
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-3 w-3 rounded-full border-[3px]" style={{ borderColor: CRITICAL }} />
          {t.ghsAlertLabel}
        </span>
      </div>
    </div>
  );
}
