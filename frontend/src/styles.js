// Colours shared by the CHV and nurse screens
export const RISK_STYLE = {
  HIGH: "bg-red-100 text-red-700 ring-red-200",
  MEDIUM: "bg-amber-100 text-amber-800 ring-amber-200",
  LOW: "bg-emerald-100 text-emerald-700 ring-emerald-200",
};

// Referral progress, set by the facility nurse
export const REFERRAL_STYLE = {
  pending: "bg-amber-100 text-amber-800",
  arrived: "bg-sky-100 text-sky-800",
  completed: "bg-emerald-100 text-emerald-800",
};

export const inputClass =
  "w-full rounded-xl border border-stone-300 bg-white px-4 py-3 text-sm outline-none transition focus:border-teal-600 focus:ring-4 focus:ring-teal-100";
