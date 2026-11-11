import { useState, useEffect } from "react";
import Logo from "./Logo";
import LanguageSelect from "./LanguageSelect";
import { FingerprintSetup } from "./Fingerprint";

const ROLE_NAMES = {
  chv: "Community Health Volunteer",
  nurse: "Facility Nurse / Midwife",
  doctor: "Doctor / Specialist",
  pharmacist: "Pharmacist",
  ghs: "GHS Officer",
  admin: "System Admin",
};

export default function Header({ user, t, lang, setLang, onLogout }) {
  const [isOnline, setIsOnline] = useState(navigator.onLine);

  useEffect(() => {
    const on = () => setIsOnline(true);
    const off = () => setIsOnline(false);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => {
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
    };
  }, []);

  return (
    <header className="sticky top-0 z-10 border-b border-stone-200 bg-white/90 backdrop-blur">
      <div className="mx-auto flex max-w-5xl items-center justify-between gap-3 px-4 py-3">
        <div className="flex items-center gap-3">
          <Logo size={36} />
          <div className="leading-tight">
            <p className="font-semibold text-teal-800">{t.appName}</p>
            <p className="text-xs text-stone-500">{ROLE_NAMES[user.role]}</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span
            className={`hidden items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium sm:flex ${
              isOnline ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"
            }`}
          >
            <span className={`h-2 w-2 rounded-full ${isOnline ? "bg-emerald-500" : "bg-amber-500"}`} />
            {isOnline ? t.online : t.offline}
          </span>
          <LanguageSelect lang={lang} setLang={setLang} className="text-xs" />
          <FingerprintSetup t={t} />
          <div className="hidden text-right leading-tight md:block">
            <p className="text-sm font-medium text-stone-800">{user.full_name}</p>
            <p className="text-xs text-stone-500">{user.facility}</p>
          </div>
          <button
            onClick={onLogout}
            className="rounded-full bg-stone-800 px-3 py-1.5 text-xs font-medium text-white hover:bg-stone-900"
          >
            {t.logout}
          </button>
        </div>
      </div>
    </header>
  );
}
