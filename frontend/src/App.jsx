import { useState, useEffect } from "react";
import { api } from "./api";
import { getText } from "./i18n";
import Login from "./Login";
import ChvApp from "./ChvApp";
import InboxApp from "./InboxApp";
import GhsApp from "./GhsApp";
import AdminApp from "./AdminApp";
import ChangePassword from "./ChangePassword";

// Sessions from before offline encryption have no key: make them log in again
if (sessionStorage.getItem("hc_token") && !sessionStorage.getItem("hc_key")) sessionStorage.clear();

export default function App() {
  const [lang, setLang] = useState("en");
  const [user, setUser] = useState(null);
  // Only need to check with the backend if a token was saved earlier
  const [checking, setChecking] = useState(() => Boolean(sessionStorage.getItem("hc_token")));
  const t = getText(lang);

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

  if (!user) return <Login onLogin={handleLogin} t={t} lang={lang} setLang={setLang} />;

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
  if (user.role === "ghs") return <GhsApp {...shared} />;
  if (user.role === "admin") return <AdminApp {...shared} />;
  return null;
}
