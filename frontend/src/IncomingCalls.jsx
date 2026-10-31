import { useEffect, useState } from "react";
import { api } from "./api";

// "Test CHV One is calling about Yaw: Join" banner. Checks every 5 seconds.
export default function IncomingCalls({ t, onJoin }) {
  const [calls, setCalls] = useState([]);

  useEffect(() => {
    const check = () => api("/calls/active").then(setCalls).catch(() => {});
    check();
    const timer = setInterval(check, 5000);
    return () => clearInterval(timer);
  }, []);

  if (calls.length === 0) return null;
  return (
    <div className="mb-5 space-y-2">
      {calls.map((c) => (
        <div
          key={c.referral_id}
          className="flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-emerald-600 px-4 py-3 text-white shadow-lg"
        >
          <p className="text-sm">
            <span className="mr-1 animate-pulse">📞</span>
            <span className="font-semibold">{c.caller?.name}</span> {t.isCallingAbout}{" "}
            <span className="font-semibold">{c.full_name}</span> <span className="font-mono text-xs">({c.ref})</span>
          </p>
          <button
            onClick={() => onJoin(c.referral_id, c.full_name)}
            className="rounded-xl bg-white px-4 py-2 text-sm font-semibold text-emerald-700 hover:bg-emerald-50"
          >
            {t.joinCall}
          </button>
        </div>
      ))}
    </div>
  );
}
