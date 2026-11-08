import { useState, useEffect } from "react";
import Logo from "./Logo";
import Icon from "./Icon";
import LanguageSelect from "./LanguageSelect";

// Each menu item gets its own colour, so people can find it by colour as well as by word
const ITEM_COLOURS = ["#d6f3e0", "#dcecfc", "#ffeccb", "#ece5fc", "#fde3e0", "#d5f1f2"];

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
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-64 flex-col border-r border-stone-200 bg-white text-stone-700 lg:flex">
        <div className="flex items-center gap-3 px-5 pb-6 pt-6">
          <Logo size={36} />
          <div className="leading-tight">
            <p className="font-display text-lg font-bold text-stone-800">HealthConnect</p>
            <p className="text-xs text-stone-500">by Storm Surfers</p>
          </div>
        </div>
        <nav aria-label="Main" className="flex-1 space-y-1 overflow-y-auto px-3">
          {items.map((item, i) => (
            <button
              key={item.key}
              onClick={() => onSelect(item.key)}
              aria-current={active === item.key ? "page" : undefined}
              className={`flex w-full items-center gap-3 rounded-xl px-2.5 py-2 text-left text-sm font-medium ${
                active === item.key ? "bg-teal-50 font-semibold text-teal-800" : "text-stone-600 hover:bg-stone-100"
              }`}
            >
              <span className="rounded-lg p-1.5 text-stone-700" style={{ background: ITEM_COLOURS[i % ITEM_COLOURS.length] }}><Icon name={item.icon} size={18} /></span>
              <span className="flex-1">{item.label}</span>
              {item.count > 0 && <span className="rounded-full bg-teal-600 px-2 text-xs font-bold text-white">{item.count}</span>}
            </button>
          ))}
        </nav>
        <div className="space-y-3 border-t border-stone-200 p-5 text-stone-500">
          <div className="leading-tight">
            <p className="text-sm font-semibold text-stone-800">{user.full_name}</p>
            <p className="mt-0.5 text-xs">{ROLE_NAMES[user.role]}</p>
            {user.facility && <p className="text-xs">{user.facility}</p>}
          </div>
          <div className="flex items-center justify-between">
            {status}
            <LanguageSelect lang={lang} setLang={setLang} className="text-xs" />
          </div>
          <button onClick={onLogout} className="w-full rounded-xl border border-stone-300 py-1.5 text-xs font-medium text-stone-700 hover:bg-stone-100">
            {t.logout}
          </button>
        </div>
      </aside>

      {/* Top bar: phones */}
      <header className="sticky top-0 z-20 flex items-center justify-between gap-2 border-b border-stone-200 bg-white px-4 py-2.5 lg:hidden">
        <div className="flex items-center gap-2">
          <Logo size={30} />
          <div className="leading-none">
            <p className="font-display font-bold text-stone-800">HealthConnect</p>
            <div className="mt-1 text-stone-500">{status}</div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <LanguageSelect lang={lang} setLang={setLang} className="text-xs" />
          <button onClick={onLogout} className="rounded-lg border border-stone-300 px-2.5 py-1 text-xs font-medium text-stone-700">{t.logout}</button>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 pb-28 pt-6 lg:px-8 lg:pb-12">{children}</main>

      {/* Bottom bar: phones. Scrolls sideways if a role has many sections. */}
      <nav aria-label="Main" className="fixed inset-x-0 bottom-0 z-20 flex overflow-x-auto border-t border-stone-200 bg-white lg:hidden">
        {items.map((item, i) => (
          <button
            key={item.key}
            onClick={() => onSelect(item.key)}
            aria-current={active === item.key ? "page" : undefined}
            className={`relative flex min-w-[4.6rem] flex-1 flex-col items-center gap-1 border-t-[3px] px-1 pb-2 pt-2 text-[11px] font-medium ${
              active === item.key ? "border-teal-600 font-bold text-teal-700" : "border-transparent text-stone-500"
            }`}
          >
            <span className="rounded-lg p-1 text-stone-700" style={{ background: ITEM_COLOURS[i % ITEM_COLOURS.length] }}><Icon name={item.icon} size={20} /></span>
            {item.label}
            {item.count > 0 && <span className="absolute right-3 top-1 rounded-full bg-red-600 px-1.5 text-[10px] font-bold text-white">{item.count}</span>}
          </button>
        ))}
      </nav>
    </div>
  );
}
