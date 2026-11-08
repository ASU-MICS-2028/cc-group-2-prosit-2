import { useEffect, useState } from "react";
import { api } from "./api";

// "Test CHV One is calling about Yaw: Join" banner. Checks every 3 seconds.
export default function IncomingCalls({ t, onJoin }) {
  const [calls, setCalls] = useState([]);

  useEffect(() => {
    const check = () => api("/calls/active").then(setCalls).catch(() => {});
    check();
    const timer = setInterval(check, 3000);
    return () => clearInterval(timer);
  }, []);

  // Ring and vibrate while a call is waiting, so staff notice without looking at the screen
  const ringing = calls.length > 0;
  useEffect(() => {
    if (!ringing) return;
    const ring = () => {
      navigator.vibrate?.(400);
      try {
        const sound = new AudioContext();
        const tone = sound.createOscillator();
        tone.frequency.value = 660;
        tone.connect(sound.destination);
        tone.start();
        tone.stop(sound.currentTime + 0.35);
        tone.onended = () => sound.close();
      } catch {
        // No sound available: the banner still shows
      }
    };
    ring();
    const timer = setInterval(ring, 2000);
    return () => clearInterval(timer);
  }, [ringing]);

  if (calls.length === 0) return null;
  // Fixed to the screen: visible on every section, however far the page is scrolled
  return (
    <div role="alert" className="fixed inset-x-3 top-3 z-40 space-y-2 lg:left-[17.5rem] lg:right-6">
      {calls.map((c) => (
        <div
          key={c.referral_id}
          className="flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-emerald-600 px-4 py-3 text-white shadow-lg"
        >
          <p className="text-sm">
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
