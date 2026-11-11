import { useState, useRef, useEffect } from "react";
import { apiBlobUrl } from "./api";

// 🔊 Listen: plays a lesson aloud in its own language, for people who cannot read it
export default function ListenButton({ t, lessonId }) {
  const [state, setState] = useState("idle"); // idle | loading | playing
  const [error, setError] = useState("");
  const audio = useRef(null);

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
        audio.current = new Audio(await apiBlobUrl(`/lessons/${lessonId}/audio`));
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
    <div className="mb-2">
      <button
        onClick={play}
        disabled={state === "loading"}
        className="rounded-full bg-teal-700 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-800 disabled:opacity-60"
      >
        {state === "loading" ? `⏳ ${t.listenLoading}` : state === "playing" ? `⏸ ${t.listenPause}` : `🔊 ${t.listen}`}
      </button>
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
    </div>
  );
}
