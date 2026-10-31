import { RISK_STYLE } from "./styles";

export default function RiskBadge({ level, t }) {
  if (!level) return <span className="rounded-full bg-stone-100 px-2.5 py-1 text-xs text-stone-500">{t.notAssessed}</span>;
  return (
    <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ${RISK_STYLE[level]}`}>{level}</span>
  );
}
