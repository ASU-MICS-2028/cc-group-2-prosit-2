import { useState, useEffect } from "react";
import { api } from "./api";
import Header from "./Header";
import { inputClass } from "./styles";

const ROLES = ["chv", "nurse", "doctor", "ghs", "admin"];
const EMPTY = { username: "", full_name: "", role: "chv", facility: "", facility_phone: "", district: "" };

// System admin: create and disable staff accounts. Never sees patient data.
export default function AdminApp(props) {
  const { t, user } = props;
  const [users, setUsers] = useState([]);
  const [districts, setDistricts] = useState([]);
  const [form, setForm] = useState(EMPTY);
  const [created, setCreated] = useState(null); // { username, temporary_password }, shown once
  const [error, setError] = useState("");

  const load = () =>
    api("/admin/users")
      .then((d) => {
        setUsers(d.users);
        setDistricts(d.districts);
      })
      .catch((err) => setError(err.message));

  useEffect(() => {
    load();
  }, []);

  const createAccount = async (e) => {
    e.preventDefault();
    setError("");
    try {
      setCreated(await api("/admin/users", { method: "POST", body: form }));
      setForm(EMPTY);
      load();
    } catch (err) {
      setError(err.message);
    }
  };

  const setActive = async (id, active) => {
    setError("");
    try {
      await api(`/admin/users/${id}/active`, { method: "POST", body: { active } });
      load();
    } catch (err) {
      setError(err.message);
    }
  };

  const field = (name) => ({ value: form[name], onChange: (e) => setForm({ ...form, [name]: e.target.value }) });
  const needsFacility = ["chv", "nurse", "doctor"].includes(form.role);

  return (
    <div className="min-h-screen bg-stone-50">
      <Header {...props} />
      <main className="mx-auto max-w-5xl px-4 py-8">
        <h1 className="text-2xl font-bold text-stone-800">{t.adminTitle}</h1>
        <p className="mt-1 text-sm text-stone-500">{t.adminHint}</p>

        {error && <p className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

        {/* Temporary password: shown once, the admin hands it over in person */}
        {created && (
          <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
            <p>
              {t.adminCreated} <strong>{created.username}</strong>. {t.adminTempPassword}
            </p>
            <p className="mt-2 font-mono text-lg font-semibold tracking-wide">{created.temporary_password}</p>
            <p className="mt-2 text-xs">{t.adminShownOnce}</p>
            <button onClick={() => setCreated(null)} className="mt-3 text-xs font-semibold underline">
              {t.adminDone}
            </button>
          </div>
        )}

        <form onSubmit={createAccount} className="mt-6 grid gap-3 rounded-2xl border border-stone-200 bg-white p-5 sm:grid-cols-2">
          <h2 className="text-lg font-semibold text-stone-800 sm:col-span-2">{t.adminNew}</h2>
          <div>
            <label className="mb-1 block text-sm font-medium text-stone-700">{t.adminUsername}</label>
            <input required pattern="[a-z0-9_]{3,30}" title={t.adminUsernameRule} className={inputClass} {...field("username")} />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-stone-700">{t.fullName}</label>
            <input required maxLength={100} className={inputClass} {...field("full_name")} />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-stone-700">{t.adminRole}</label>
            <select className={inputClass} {...field("role")}>
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {t["role_" + r]}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-stone-700">{t.adminDistrict}</label>
            <select className={inputClass} {...field("district")}>
              <option value="">{t.adminNone}</option>
              {districts.map((d) => (
                <option key={d}>{d}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-stone-700">{t.adminFacility}</label>
            <input required={needsFacility} maxLength={100} className={inputClass} {...field("facility")} />
          </div>
          {form.role === "chv" && (
            <div>
              <label className="mb-1 block text-sm font-medium text-stone-700">{t.adminFacilityPhone}</label>
              <input pattern="0\d{9}|\+?233\d{9}" placeholder="0240000000" className={inputClass} {...field("facility_phone")} />
            </div>
          )}
          <button className="rounded-xl bg-teal-700 py-3 font-semibold text-white hover:bg-teal-800 sm:col-span-2">
            {t.adminCreate}
          </button>
        </form>

        <div className="mt-6 overflow-x-auto rounded-2xl border border-stone-200 bg-white">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-stone-200 text-xs uppercase text-stone-500">
              <tr>
                <th className="px-4 py-3">{t.adminUsername}</th>
                <th className="px-4 py-3">{t.fullName}</th>
                <th className="px-4 py-3">{t.adminRole}</th>
                <th className="px-4 py-3">{t.adminFacility}</th>
                <th className="px-4 py-3">{t.adminDistrict}</th>
                <th className="px-4 py-3">{t.adminStatus}</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className={`border-b border-stone-100 ${u.active ? "" : "text-stone-400"}`}>
                  <td className="px-4 py-3 font-medium">{u.username}</td>
                  <td className="px-4 py-3">{u.full_name}</td>
                  <td className="px-4 py-3">{t["role_" + u.role]}</td>
                  <td className="px-4 py-3">{u.facility || "–"}</td>
                  <td className="px-4 py-3">{u.district || "–"}</td>
                  <td className="flex items-center gap-2 px-4 py-3">
                    <span className="w-16 text-xs">{u.active ? t.adminActive : t.adminDisabled}</span>
                    {u.id === user.id ? (
                      <span className="text-xs text-stone-500">{t.adminYou}</span>
                    ) : (
                      <button
                        onClick={() => setActive(u.id, !u.active)}
                        className={`rounded-full px-3 py-1 text-xs font-semibold ${
                          u.active ? "bg-red-50 text-red-700 hover:bg-red-100" : "bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
                        }`}
                      >
                        {u.active ? t.adminDisable : t.adminEnable}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </main>
    </div>
  );
}
