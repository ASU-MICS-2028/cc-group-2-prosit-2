import { useState, useEffect } from "react";
import { isLocked, openNote } from "./e2e";

// A note that may be end-to-end encrypted: opened here, on the phone. 🔒 shows it was private.
export default function PrivateNote({ patientId, text, className = "mt-1 text-xs italic text-stone-500" }) {
  const [shown, setShown] = useState({ text: null, problem: null });
  useEffect(() => {
    if (!isLocked(text)) return;
    let live = true;
    openNote(patientId, text)
      .then((plain) => live && setShown({ text: plain, problem: null }))
      .catch((err) => live && setShown({ text: null, problem: err.message }));
    return () => {
      live = false;
    };
  }, [patientId, text]);

  if (!text) return null;
  if (!isLocked(text)) return <p className={className}>{text}</p>;
  if (shown.problem) return <p className={`${className} text-amber-700`}>🔒 {shown.problem}</p>;
  if (shown.text === null) return <p className={className}>🔒 …</p>;
  return (
    <p className={className} title="End-to-end encrypted: only this patient's care team can read it">
      🔒 {shown.text}
    </p>
  );
}
