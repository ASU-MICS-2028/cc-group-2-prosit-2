import { useState, useEffect, useCallback } from "react";
import { api } from "./api";
import { LANGUAGES } from "./i18n";
import { cachedApi } from "./patientCache";
import LessonSlides from "./LessonSlides";
import ListenButton from "./ListenButton";
import { inputClass } from "./styles";

const TOPICS = ["malaria", "maternal", "cholera", "general"];
// Lessons can be in the app's languages and in every other language Abena AI can speak.
const LESSON_LANGUAGES = [
  ...LANGUAGES,
  { code: "gpe", name: "Ghanaian Pidgin" },
  { code: "ha", name: "Hausa" },
  { code: "pcm", name: "Nigerian Pidgin" },
  { code: "yo", name: "Yoruba" },
  { code: "sw", name: "Swahili" },
];
// Languages Abena AI can speak (backend/tts.py), and whether a male voice exists too. Ga and Dagbani: no voice yet.
const SPOKEN = { tw: true, en: true, ee: false, gpe: false, ha: false, pcm: false, yo: false, sw: false };
const BLANK = { topic: "general", title: "", body: "", language: "tw" };
const languageName = (code) => LESSON_LANGUAGES.find((l) => l.code === code)?.name || code;

// Short health lessons a CHV can read out or show. Not reviewed until a nurse or doctor approves.
export default function LessonsPanel({ t, role, userId }) {
  const [lessons, setLessons] = useState([]);
  const [open, setOpen] = useState(false);
  const [shown, setShown] = useState(null); // id of the lesson being read
  const [language, setLanguage] = useState("");
  const [writing, setWriting] = useState(false);
  const [form, setForm] = useState(BLANK);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    // Saved encrypted on the phone, so a CHV can still show lessons where there is no signal
    cachedApi(userId, "/lessons").then((r) => setLessons(r.data)).catch(() => setLessons([]));
  }, [userId]);
  useEffect(load, [load]);

  const submit = async (path, body) => {
    setError("");
    try {
      await api(path, { method: "POST", ...(body ? { body } : {}) });
      setWriting(false);
      setForm(BLANK);
      load();
    } catch (err) {
      setError(err.message);
    }
  };

  if (lessons.length === 0) return null;
  const visible = lessons.filter((l) => !language || l.language === language);
  const canReview = role === "nurse" || role === "doctor";

  return (
    <div className="mt-6 rounded-2xl border border-stone-200 bg-white p-5 text-sm">
      <button onClick={() => setOpen(!open)} className="text-lg font-semibold text-stone-800">
        {open ? "▾" : "▸"} 📚 {t.lessonsTitle}
      </button>
      {open && (
        <div className="mt-2 space-y-2">
          <p className="text-xs text-stone-500">{t.lessonsHint}</p>
          <div className="flex flex-wrap items-center gap-2">
            <select value={language} onChange={(e) => setLanguage(e.target.value)} className={`${inputClass} max-w-xs`}>
              <option value="">{t.lessonsAllLanguages}</option>
              {LESSON_LANGUAGES.map((l) => <option key={l.code} value={l.code}>{l.name}</option>)}
            </select>
            <button onClick={() => setWriting(!writing)} className="font-medium text-teal-700 hover:underline">
              + {t.lessonsWrite}
            </button>
          </div>

          {writing && (
            <div className="space-y-2 rounded-xl border border-teal-200 bg-teal-50/50 p-3">
              <select value={form.topic} onChange={(e) => setForm({ ...form, topic: e.target.value })} className={inputClass}>
                {TOPICS.map((topic) => <option key={topic} value={topic}>{t["lessonTopic_" + topic]}</option>)}
              </select>
              <select value={form.language} onChange={(e) => setForm({ ...form, language: e.target.value })} className={inputClass}>
                {LESSON_LANGUAGES.map((l) => <option key={l.code} value={l.code}>{l.name}</option>)}
              </select>
              <input placeholder={t.lessonsTitleField} value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} className={inputClass} />
              <textarea rows={4} placeholder={t.lessonsBodyField} value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })} className={inputClass} />
              <button
                onClick={() => submit("/lessons", form)}
                disabled={form.title.trim().length < 3 || form.body.trim().length < 20}
                className="rounded-xl bg-teal-700 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-800 disabled:opacity-50"
              >
                {t.saveChanges}
              </button>
            </div>
          )}
          {error && <p className="text-sm text-red-600">{error}</p>}

          {visible.map((l) => (
            <div key={l.id} className="rounded-xl border border-stone-200 p-3">
              <button onClick={() => setShown(shown === l.id ? null : l.id)} className="flex w-full flex-wrap items-center justify-between gap-2 text-left">
                <span className="font-semibold text-stone-900">{l.title}</span>
                <span className="text-xs">
                  <span className="text-stone-500">{languageName(l.language)}</span>{" "}
                  <span className={`rounded-full px-2 py-0.5 font-semibold ${l.reviewed_at ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"}`}>
                    {l.reviewed_at ? `✓ ${t.lessonsReviewed}` : t.lessonsNotReviewed}
                  </span>
                </span>
              </button>
              {shown === l.id && (
                <div className="mt-2">
                  {l.language in SPOKEN ? <ListenButton t={t} lessonId={l.id} twoVoices={SPOKEN[l.language]} /> : <p className="mb-2 text-xs text-stone-500">{t.listenNoVoice}</p>}
                  <LessonSlides t={t} body={l.body} />
                  <p className="mt-2 whitespace-pre-wrap text-xs text-stone-500">{l.body}</p>
                  {l.reviewer_name && <p className="mt-1 text-xs text-stone-500">{t.lessonsReviewedBy} {l.reviewer_name}</p>}
                  {canReview && !l.reviewed_at && (
                    <button onClick={() => submit(`/lessons/${l.id}/review`)} className="mt-2 rounded-xl border border-stone-300 px-3 py-1.5 text-xs font-medium text-stone-700 hover:bg-stone-100">
                      {t.lessonsApprove}
                    </button>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
