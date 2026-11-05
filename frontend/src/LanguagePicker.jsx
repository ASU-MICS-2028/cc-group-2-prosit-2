import { LANGUAGES } from "./i18n";

// One picker for the login page and the header. Each language is named in itself.
export default function LanguagePicker({ lang, setLang, className = "" }) {
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
