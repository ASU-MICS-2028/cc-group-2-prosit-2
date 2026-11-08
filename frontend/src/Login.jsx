import { useState } from "react";
import { api } from "./api";
import Logo from "./Logo";
import LanguageSelect from "./LanguageSelect";

const DEMO_USERS = ["chv1", "chv2", "nurse1", "nurse2", "doctor1", "pharm1", "ghs1", "admin1"];

export default function Login({ onLogin, t, lang, setLang }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const data = await api("/auth/login", { method: "POST", body: { username, password } });
      onLogin(data.token, data.user, data.offline_key);
    } catch (err) {
      setError(err.message);
    }
    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-stone-50">
      {/* Brand panel */}
      {/* Form panel */}
      <div className="flex min-h-screen flex-col items-center justify-center p-6">
        <div className="w-full max-w-sm">
          <div className="mb-8 flex flex-col items-center text-center">
            <Logo size={56} />
            <h1 className="mt-3 text-3xl font-extrabold text-teal-800">HealthConnect</h1>
            <p className="font-display font-semibold text-stone-700">by Storm Surfers</p>
            <p className="text-sm text-stone-500">{t.tagline}</p>
          </div>

          <h2 className="text-2xl font-bold text-stone-800">{t.welcome}</h2>
          <p className="mt-1 text-sm text-stone-500">{t.signInHint}</p>

          <form onSubmit={handleSubmit} className="mt-6 space-y-4">
            <div>
              <label className="mb-1 block text-sm font-medium text-stone-700">{t.username}</label>
              <input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                required
                className="w-full rounded-xl border border-stone-300 bg-white px-4 py-3 text-sm outline-none transition focus:border-teal-600 focus:ring-4 focus:ring-teal-100"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-stone-700">{t.password}</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                required
                className="w-full rounded-xl border border-stone-300 bg-white px-4 py-3 text-sm outline-none transition focus:border-teal-600 focus:ring-4 focus:ring-teal-100"
              />
            </div>

            {error && (
              <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-xl bg-teal-700 py-3 font-semibold text-white transition hover:bg-teal-800 disabled:opacity-60"
            >
              {loading ? t.signingIn : t.login}
            </button>
          </form>

          {/* Only shown when running locally (npm run dev), never in a production build */}
          {import.meta.env.DEV && (
            <div className="mt-6 rounded-xl border border-dashed border-amber-300 bg-amber-50 p-3 text-xs text-amber-900">
              <p className="font-semibold">{t.demoAccounts}</p>
              <p className="mt-1">
                {DEMO_USERS.map((u) => (
                  <button
                    key={u}
                    type="button"
                    onClick={() => setUsername(u)}
                    className="mr-1 mt-1 rounded bg-white px-2 py-0.5 font-mono ring-1 ring-amber-200 hover:bg-amber-100"
                  >
                    {u}
                  </button>
                ))}
              </p>
              <p className="mt-2">Password: <span className="font-mono">Demo@1234</span></p>
            </div>
          )}

          <div className="mt-6 flex items-center justify-between text-sm">
            <LanguageSelect lang={lang} setLang={setLang} />
            <span className="text-xs text-stone-400">Storm Surfers · Group 2</span>
          </div>
        </div>
      </div>
    </div>
  );
}
