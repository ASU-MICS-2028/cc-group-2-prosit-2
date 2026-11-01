import { useState } from "react";
import { api } from "./api";
import Logo from "./Logo";
import { inputClass } from "./styles";

// Shown after login while the account still has a temporary password.
// The server blocks every other action until this is done.
export default function ChangePassword({ user, t, onChanged, onLogout }) {
  const [form, setForm] = useState({ current: "", next: "", confirm: "" });
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    if (form.next !== form.confirm) return setError(t.pwMismatch);
    setSaving(true);
    try {
      await api("/auth/change-password", {
        method: "POST",
        body: { current_password: form.current, new_password: form.next },
      });
      onChanged();
    } catch (err) {
      setError(err.message);
    }
    setSaving(false);
  };

  const field = (name, autoComplete) => ({
    type: "password",
    required: true,
    autoComplete,
    value: form[name],
    onChange: (e) => setForm({ ...form, [name]: e.target.value }),
    className: inputClass,
  });

  return (
    <div className="flex min-h-screen items-center justify-center bg-stone-50 p-6">
      <form onSubmit={submit} className="w-full max-w-sm space-y-4 rounded-2xl border border-stone-200 bg-white p-6">
        <Logo size={44} />
        <div>
          <h1 className="text-xl font-bold text-stone-800">{t.pwTitle}</h1>
          <p className="mt-1 text-sm text-stone-500">
            {user.full_name}: {t.pwHint}
          </p>
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-stone-700">{t.pwCurrent}</label>
          <input {...field("current", "current-password")} />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-stone-700">{t.pwNew}</label>
          <input {...field("next", "new-password")} minLength={8} maxLength={72} />
          <p className="mt-1 text-xs text-stone-500">{t.pwRule}</p>
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-stone-700">{t.pwConfirm}</label>
          <input {...field("confirm", "new-password")} />
        </div>
        {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
        <button disabled={saving} className="w-full rounded-xl bg-teal-700 py-3 font-semibold text-white hover:bg-teal-800 disabled:opacity-60">
          {t.pwSave}
        </button>
        <button type="button" onClick={onLogout} className="w-full text-sm text-stone-500 hover:underline">
          {t.logout}
        </button>
      </form>
    </div>
  );
}
