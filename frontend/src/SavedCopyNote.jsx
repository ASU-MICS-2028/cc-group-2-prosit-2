// Shown when a screen is the phone's saved copy, not fresh from the server
export default function SavedCopyNote({ t, savedAt }) {
  return (
    <p className="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800">
      {t.savedCopy} {new Date(savedAt).toLocaleString()}
    </p>
  );
}
