import { LANGUAGES } from "./i18n";

// Dropdown to pick the app's language; used on the sign-in page and in the header
export default function LanguageSelect({ lang, setLang, className = "" }) {
  return (
    <select
      value={lang}
      onChange={(e) => setLang(e.target.value)}
      aria-label="Language"
      className={`rounded-full border border-stone-300 bg-white px-3 py-1 text-stone-600 hover:bg-stone-100 ${className}`}
    >
      {LANGUAGES.map((l) => (
        <option key={l.code} value={l.code}>
          {l.name}
        </option>
      ))}
    </select>
  );
}
