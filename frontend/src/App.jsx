import { useState, useEffect } from "react";
import { api } from "./api";
import { getText } from "./i18n";
import Splash from "./Splash";
import Login from "./Login";
import ChvApp from "./ChvApp";
import InboxApp from "./InboxApp";
import PharmacistApp from "./PharmacistApp";
import GhsApp from "./GhsApp";
import AdminApp from "./AdminApp";
import ChangePassword from "./ChangePassword";

// Sessions from before offline encryption have no key: make them log in again
if (sessionStorage.getItem("hc_token") && !sessionStorage.getItem("hc_key")) sessionStorage.clear();

export default function App() {
  const [lang, setLang] = useState("en");
  const [user, setUser] = useState(null);
  const [splash, setSplash] = useState(true); // the opening fade, once per visit
  // Only need to check with the backend if a token was saved earlier
  const [checking, setChecking] = useState(() => Boolean(sessionStorage.getItem("hc_token")));
  const t = getText(lang);

  // Must match the 5.4s animation in index.css
  useEffect(() => {
    const timer = setTimeout(() => setSplash(false), 5400);
    return () => clearTimeout(timer);
  }, []);

  // On page load, ask the backend if the saved token is still valid
  useEffect(() => {
    if (!sessionStorage.getItem("hc_token")) return;
    api("/auth/me")
      .then(setUser)
      .catch((err) => {
        // No signal (fetch fails with TypeError): stay logged in with the saved details.
        // Any other error means the token is bad: log out.
        if (err instanceof TypeError) setUser(JSON.parse(sessionStorage.getItem("hc_user")));
        else sessionStorage.clear();
      })
      .finally(() => setChecking(false));
  }, []);

  const handleLogin = (token, userInfo, offlineKey) => {
    // sessionStorage is wiped when the tab closes (safer on shared phones)
    sessionStorage.setItem("hc_token", token);
    sessionStorage.setItem("hc_key", offlineKey);
    sessionStorage.setItem("hc_user", JSON.stringify(userInfo));
    setUser(userInfo);
  };

  const handleLogout = () => {
    sessionStorage.clear();
    setUser(null);
  };

  if (checking) return null;

  if (!user) {
    return (
      <>
        {splash && <Splash onSkip={() => setSplash(false)} />}
        <Login onLogin={handleLogin} t={t} lang={lang} setLang={setLang} />
      </>
    );
  }

  // Temporary password (new or reset account): must set a new one first
  if (user.must_change_password) {
    const done = () => {
      const updated = { ...user, must_change_password: false };
      sessionStorage.setItem("hc_user", JSON.stringify(updated));
      setUser(updated);
    };
    return <ChangePassword user={user} t={t} onChanged={done} onLogout={handleLogout} />;
  }

  // RBAC on the screen side: each role gets its own workspace.
  // The backend still checks the role on every request.
  const shared = { user, t, lang, setLang, onLogout: handleLogout };
  if (user.role === "chv") return <ChvApp {...shared} />;
  if (user.role === "nurse" || user.role === "doctor") return <InboxApp {...shared} />;
  if (user.role === "pharmacist") return <PharmacistApp {...shared} />;
  if (user.role === "ghs") return <GhsApp {...shared} />;
  if (user.role === "admin") return <AdminApp {...shared} />;

  // A role this copy of the app doesn't know: usually an old copy saved on the phone (PWA)
  // from before the role existed. Say so instead of showing a blank page.
  return (
    <div className="flex min-h-screen items-center justify-center bg-stone-50 p-6">
      <div className="max-w-sm rounded-2xl border border-stone-200 bg-white p-6 text-center">
        <p className="text-stone-800">{t.unknownRole}</p>
        <div className="mt-4 flex justify-center gap-2">
          <button onClick={() => window.location.reload()} className="rounded-xl bg-teal-700 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-800">
            {t.reloadApp}
          </button>
          <button onClick={handleLogout} className="rounded-xl px-4 py-2 text-sm text-stone-600 hover:bg-stone-100">
            {t.logout}
          </button>
        </div>
      </div>
    </div>
  );
}
