import { useState, useEffect, useMemo } from "react";
import { lessonSteps } from "./lessonSteps";

const STEP_SECONDS = 6;
const button = "rounded-lg border border-stone-300 px-3 py-1 text-sm font-medium text-stone-700 hover:bg-stone-100 disabled:opacity-40";

// Plays a lesson as animated picture steps. Drawn by the phone, so there is no video to download.
export default function LessonSlides({ t, body }) {
  const steps = useMemo(() => lessonSteps(body), [body]);
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const last = steps.length - 1;

  useEffect(() => {
    if (!playing) return undefined;
    const timer = setInterval(() => {
      setIndex((i) => Math.min(i + 1, last));
    }, STEP_SECONDS * 1000);
    return () => clearInterval(timer);
  }, [playing, last]);

  // Stop at the last picture rather than looping
  const atEnd = index >= last;
  const isPlaying = playing && !atEnd;

  if (steps.length === 0) return null;
  const step = steps[Math.min(index, last)];

  const togglePlay = () => {
    if (atEnd) setIndex(0);
    setPlaying(atEnd ? true : !playing);
  };

  return (
    <div className="rounded-xl bg-teal-50 p-4 text-center">
      <style>{`
        @keyframes lesson-step { from { opacity: 0; transform: translateY(14px) scale(.92); } to { opacity: 1; transform: none; } }
        @keyframes lesson-bob { 50% { transform: translateY(-8px); } }
        .lesson-step { animation: lesson-step .5s ease-out; }
        .lesson-picture { display: inline-block; animation: lesson-bob 2s ease-in-out infinite; }
        @media (prefers-reduced-motion: reduce) { .lesson-step, .lesson-picture { animation: none; } }
      `}</style>
      <div key={index} className="lesson-step" style={{ minHeight: 150 }}>
        <span className="lesson-picture text-6xl" role="img" aria-hidden="true">{step.picture}</span>
        <p className="mt-3 text-lg font-medium leading-snug text-stone-900">{step.text}</p>
      </div>
      <div className="mt-3 flex justify-center gap-1.5" aria-hidden="true">
        {steps.map((s, i) => (
          <span key={s.text} className={`h-2 w-2 rounded-full ${i === index ? "bg-teal-700" : "bg-teal-200"}`} />
        ))}
      </div>
      <p className="mt-1 text-xs text-stone-500">{t.lessonsStep} {index + 1} / {steps.length}</p>
      <div className="mt-2 flex justify-center gap-2">
        <button onClick={() => { setPlaying(false); setIndex(index - 1); }} disabled={index === 0} className={button}>◀</button>
        <button onClick={togglePlay} className={button}>{isPlaying ? `⏸ ${t.lessonsPause}` : `▶ ${t.lessonsPlay}`}</button>
        <button onClick={() => { setPlaying(false); setIndex(index + 1); }} disabled={atEnd} className={button}>▶▏</button>
      </div>
    </div>
  );
}
