import { useState, useEffect } from "react";
import Logo from "./Logo";
import Icon from "./Icon";
import LanguageSelect from "./LanguageSelect";

const ROLE_NAMES = {
  chv: "Community Health Volunteer",
  nurse: "Facility Nurse / Midwife",
  doctor: "Doctor / Specialist",
  pharmacist: "Pharmacist",
  ghs: "GHS Officer",
  admin: "System Admin",
};

// The frame around every signed-in screen.
// items = [{ key, label, icon, count }]: the menu for this role.
// Computers get a side menu; phones get a bottom bar within reach of the thumb.
export default function AppShell({ user, t, lang, setLang, onLogout, items, active, onSelect, children }) {
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

  const status = (
    <span className="flex items-center gap-1.5 text-xs">
      <span className={`h-2 w-2 rounded-full ${isOnline ? "bg-emerald-400" : "bg-marigold"}`} />
      {isOnline ? t.online : t.offline}
    </span>
  );

  return (
    <div className="min-h-screen bg-stone-50 lg:pl-64">
      {/* Side menu: computers */}
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-64 flex-col bg-teal-900 text-stone-100 lg:flex">
        <div className="flex items-center gap-3 px-5 pb-6 pt-6">
          <Logo size={36} />
          <div className="leading-tight">
            <p className="font-display text-lg font-bold">HealthConnect</p>
            <p className="text-xs text-teal-200">by Storm Surfers</p>
          </div>
        </div>
        <nav aria-label="Main" className="flex-1 space-y-0.5 overflow-y-auto px-3">
          {items.map((item) => (
            <button
              key={item.key}
              onClick={() => onSelect(item.key)}
              aria-current={active === item.key ? "page" : undefined}
              className={`flex w-full items-center gap-3 border-l-[3px] px-3 py-2.5 text-left text-sm font-medium ${
                active === item.key ? "border-marigold bg-teal-800 text-white" : "border-transparent text-teal-100 hover:bg-teal-800/60"
              }`}
            >
              <Icon name={item.icon} />
              <span className="flex-1">{item.label}</span>
              {item.count > 0 && <span className="rounded-full bg-marigold px-2 text-xs font-bold text-teal-900">{item.count}</span>}
            </button>
          ))}
        </nav>
        <div className="space-y-3 border-t border-teal-800 p-5 text-teal-100">
          <div className="leading-tight">
            <p className="text-sm font-semibold text-white">{user.full_name}</p>
            <p className="mt-0.5 text-xs">{ROLE_NAMES[user.role]}</p>
            {user.facility && <p className="text-xs">{user.facility}</p>}
          </div>
          <div className="flex items-center justify-between">
            {status}
            <LanguageSelect lang={lang} setLang={setLang} className="text-xs" />
          </div>
          <button onClick={onLogout} className="w-full border border-teal-600 py-1.5 text-xs font-medium hover:bg-teal-800">
            {t.logout}
          </button>
        </div>
      </aside>

      {/* Top bar: phones */}
      <header className="sticky top-0 z-20 flex items-center justify-between gap-2 bg-teal-900 px-4 py-2.5 text-stone-100 lg:hidden">
        <div className="flex items-center gap-2">
          <Logo size={30} />
          <div className="leading-none">
            <p className="font-display font-bold">HealthConnect</p>
            <div className="mt-1 text-teal-200">{status}</div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <LanguageSelect lang={lang} setLang={setLang} className="text-xs" />
          <button onClick={onLogout} className="border border-teal-600 px-2.5 py-1 text-xs font-medium">{t.logout}</button>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 pb-28 pt-6 lg:px-8 lg:pb-12">{children}</main>

      {/* Bottom bar: phones. Scrolls sideways if a role has many sections. */}
      <nav aria-label="Main" className="fixed inset-x-0 bottom-0 z-20 flex overflow-x-auto border-t border-stone-200 bg-white lg:hidden">
        {items.map((item) => (
          <button
            key={item.key}
            onClick={() => onSelect(item.key)}
            aria-current={active === item.key ? "page" : undefined}
            className={`relative flex min-w-[4.6rem] flex-1 flex-col items-center gap-1 border-t-[3px] px-1 pb-2 pt-2 text-[11px] font-medium ${
              active === item.key ? "border-teal-700 text-teal-800" : "border-transparent text-stone-500"
            }`}
          >
            <Icon name={item.icon} size={22} />
            {item.label}
            {item.count > 0 && <span className="absolute right-3 top-1 rounded-full bg-red-600 px-1.5 text-[10px] font-bold text-white">{item.count}</span>}
          </button>
        ))}
      </nav>
    </div>
  );
}
