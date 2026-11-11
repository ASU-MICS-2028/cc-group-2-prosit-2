import { useState, useRef, useEffect } from "react";
import { apiBlobUrl } from "./api";

// 🔊 Listen: plays a lesson aloud in its own language, for people who cannot read it
export default function ListenButton({ t, lessonId, twoVoices }) {
  const [state, setState] = useState("idle"); // idle | loading | playing
  const [error, setError] = useState("");
  const [gender, setGender] = useState("female");
  const audio = useRef(null);

  const choose = (g) => {
    audio.current?.pause();
    audio.current = null; // the other voice is a different recording
    setState("idle");
    setGender(g);
  };

  useEffect(() => () => audio.current?.pause(), []); // stop when the lesson closes

  const play = async () => {
    if (state === "playing") {
      audio.current.pause();
      setState("idle");
      return;
    }
    setError("");
    try {
      if (!audio.current) {
        setState("loading");
        audio.current = new Audio(await apiBlobUrl(`/lessons/${lessonId}/audio${twoVoices ? `?gender=${gender}` : ""}`));
        audio.current.onended = () => setState("idle");
      }
      await audio.current.play();
      setState("playing");
    } catch (err) {
      setError(err.message);
      setState("idle");
    }
  };

  return (
    <div className="mb-2 flex flex-wrap items-center gap-2">
      <button
        onClick={play}
        disabled={state === "loading"}
        className="rounded-full bg-teal-700 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-800 disabled:opacity-60"
      >
        {state === "loading" ? `⏳ ${t.listenLoading}` : state === "playing" ? `⏸ ${t.listenPause}` : `🔊 ${t.listen}`}
      </button>
      {twoVoices &&
        ["female", "male"].map((g) => (
          <button
            key={g}
            onClick={() => choose(g)}
            title={t["voice_" + g]}
            className={`rounded-full border px-2.5 py-1.5 text-sm ${gender === g ? "border-teal-700 bg-teal-50" : "border-stone-300"}`}
          >
            {g === "female" ? "👩" : "👨"}
          </button>
        ))}
      {error && <p className="w-full text-xs text-red-600">{error}</p>}
    </div>
  );
}
