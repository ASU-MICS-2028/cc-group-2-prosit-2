import { useState, useEffect } from "react";
import { startAuthentication, startRegistration, platformAuthenticatorIsAvailable } from "@simplewebauthn/browser";
import { api } from "./api";

// Sign in with the phone's own lock (fingerprint, face or PIN) instead of typing a password.
// The fingerprint never leaves the phone: the phone signs a one-time challenge (see backend/passkeys.py).

function usePhoneLock() {
  const [available, setAvailable] = useState(false);
  useEffect(() => {
    platformAuthenticatorIsAvailable().then(setAvailable).catch(() => setAvailable(false));
  }, []);
  return available;
}

// Sign-in page: one button, no username or password
export function FingerprintSignIn({ t, onLogin, setError }) {
  const available = usePhoneLock();
  const [busy, setBusy] = useState(false);
  if (!available) return null;

  const signIn = async () => {
    setError("");
    setBusy(true);
    try {
      const origin = window.location.origin;
      const optionsJSON = await api("/auth/passkey/login/options", { method: "POST", body: { origin } });
      const credential = await startAuthentication({ optionsJSON });
      const data = await api("/auth/passkey/login/verify", { method: "POST", body: { origin, credential } });
      onLogin(data.token, data.user, data.offline_key);
    } catch (err) {
      setError(err.name === "NotAllowedError" ? t.fingerprintCancelled : err.message);
    }
    setBusy(false);
  };

  return (
    <button
      type="button"
      onClick={signIn}
      disabled={busy}
      className="mt-3 flex w-full items-center justify-center gap-2 rounded-xl border-2 border-teal-700 py-3 font-semibold text-teal-800 transition hover:bg-teal-50 disabled:opacity-60"
    >
      👆 {t.fingerprintSignIn}
    </button>
  );
}

// Top bar: turn fingerprint sign-in on for this phone (after a normal sign-in)
export function FingerprintSetup({ t }) {
  const available = usePhoneLock();
  const [done, setDone] = useState(false);
  if (!available) return null;

  const setUp = async () => {
    try {
      const origin = window.location.origin;
      const optionsJSON = await api("/auth/passkey/register/options", { method: "POST", body: { origin } });
      const credential = await startRegistration({ optionsJSON });
      await api("/auth/passkey/register/verify", { method: "POST", body: { origin, credential, label: navigator.platform || "" } });
      setDone(true);
      window.alert(t.fingerprintReady);
    } catch (err) {
      if (err.name === "InvalidStateError") window.alert(t.fingerprintAlready);
      else if (err.name !== "NotAllowedError") window.alert(err.message);
    }
  };

  return (
    <button
      onClick={setUp}
      title={t.fingerprintSetup}
      className="rounded-full border border-teal-200 px-2.5 py-1.5 text-xs font-medium text-teal-800 hover:bg-teal-50"
    >
      👆 {done ? "✓" : <span className="hidden sm:inline">{t.fingerprintSetupShort}</span>}
    </button>
  );
}
