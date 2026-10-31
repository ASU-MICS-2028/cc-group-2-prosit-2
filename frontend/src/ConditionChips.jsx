// "Check for: Malaria, Meningitis" chips. Input is a comma-separated string or an array.
export default function ConditionChips({ conditions, t }) {
  const list = Array.isArray(conditions) ? conditions : (conditions || "").split(",").filter(Boolean);
  if (list.length === 0) return null;
  return (
    <div className="mt-2 flex flex-wrap items-center gap-1.5">
      <span className="text-xs font-medium text-stone-500">{t.checkFor}:</span>
      {list.map((c) => (
        <span key={c} className="rounded-full bg-violet-100 px-2 py-0.5 text-xs font-medium text-violet-800">
          {t["cond_" + c] || c}
        </span>
      ))}
    </div>
  );
}
