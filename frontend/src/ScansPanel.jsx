import { useState, useEffect } from "react";
import { api, apiBlobUrl } from "./api";
import { inputClass } from "./styles";

const MAX_MB = 25;
// CT numbers are Hounsfield units, the same on every machine, so fixed presets work for CT.
// For X-rays the numbers differ by machine: use the sliders instead.
const CT_PRESETS = [
  { key: "scanSoftTissue", center: 40, width: 400 },
  { key: "scanLung", center: -600, width: 1500 },
  { key: "scanBone", center: 400, width: 1800 },
];
const MODALITY = { CR: "scanXray", DX: "scanXray", CT: "scanCT", US: "scanUltrasound", MR: "scanMRI" };

// A .dcm file -> base64 text, in pieces (one huge string at once can crash a phone browser)
async function toBase64(file) {
  const bytes = new Uint8Array(await file.arrayBuffer());
  let text = "";
  for (let i = 0; i < bytes.length; i += 0x8000) text += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(text);
}

function Preview({ scanId, window: win, className, onClick }) {
  const [src, setSrc] = useState(null);
  useEffect(() => {
    let url;
    const query = win ? `?center=${win.center}&width=${win.width}` : "";
    apiBlobUrl(`/scans/${scanId}/preview${query}`)
      .then((u) => setSrc((url = u)))
      .catch(() => {});
    return () => url && URL.revokeObjectURL(url);
  }, [scanId, win]);
  return src ? <img src={src} alt="" onClick={onClick} className={className} /> : <div className={`${className} animate-pulse bg-stone-800`} />;
}

// Medical scans (DICOM): nurses and doctors add them; the patient's CHV can look at the preview
export default function ScansPanel({ t, patientId, userId, canUpload }) {
  const [scans, setScans] = useState([]);
  const [adding, setAdding] = useState(false);
  const [caption, setCaption] = useState("");
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [open, setOpen] = useState(null); // the scan being viewed
  const [win, setWin] = useState(null); // contrast chosen by the viewer: { center, width }
  const [draft, setDraft] = useState(null); // slider position while dragging

  const load = () => api(`/patients/${patientId}/scans`).then(setScans).catch((err) => setError(err.message));
  useEffect(() => {
    load();
  }, [patientId]); // eslint-disable-line react-hooks/exhaustive-deps

  const upload = async (file) => {
    if (!file) return;
    if (file.size > MAX_MB * 1_000_000) return setError(t.scanTooLarge);
    setBusy(true);
    setError("");
    try {
      await api(`/patients/${patientId}/scans`, { method: "POST", body: { caption, consent, file: await toBase64(file) } });
      setAdding(false);
      setCaption("");
      setConsent(false);
      load();
    } catch (err) {
      setError(err.message);
    }
    setBusy(false);
  };
  const view = (scan) => {
    setOpen(scan);
    setWin(null);
    setDraft(scan.win_center === null ? null : { center: scan.win_center, width: scan.win_width });
  };
  const download = async (scan) => {
    try {
      const a = document.createElement("a");
      a.href = await apiBlobUrl(`/scans/${scan.id}/dicom`);
      a.download = `scan-${scan.id}.dcm`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 10_000);
    } catch (err) {
      setError(err.message);
    }
  };
  const remove = async (scan) => {
    if (!window.confirm(t.scanDeleteConfirm)) return;
    await api(`/scans/${scan.id}`, { method: "DELETE" }).catch((err) => setError(err.message));
    setOpen(null);
    load();
  };

  if (!canUpload && scans.length === 0) return null; // CHVs only see scans that facilities added
  const label = (s) => t[MODALITY[s.modality]] || s.modality || t.scanTitle;
  const range = open && open.value_min !== null ? open.value_max - open.value_min : 0;

  return (
    <div className="mt-4 rounded-2xl border border-stone-200 bg-white p-4">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold text-stone-800">🩻 {t.scanTitle} ({scans.length})</h2>
        {canUpload && !adding && (
          <button onClick={() => setAdding(true)} className="text-sm font-semibold text-teal-700 hover:underline">
            + {t.scanAdd}
          </button>
        )}
      </div>
      <p className="text-xs text-stone-500">{t.scanHint}</p>

      {adding && (
        <div className="mt-3 space-y-2 rounded-xl bg-teal-50/60 p-3">
          <input value={caption} onChange={(e) => setCaption(e.target.value)} maxLength={200} placeholder={t.photoCaption} className={inputClass} />
          <label className="flex items-start gap-2 text-sm text-stone-700">
            <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} className="mt-1" />
            <span>{t.scanConsent}</span>
          </label>
          <div className="flex items-center gap-2">
            <label className={`rounded-xl px-4 py-2 text-sm font-semibold text-white ${consent && !busy ? "cursor-pointer bg-teal-700 hover:bg-teal-800" : "bg-teal-700/40"}`}>
              {busy ? t.photoUploading : `🩻 ${t.scanChoose}`}
              <input type="file" accept=".dcm,application/dicom" disabled={!consent || busy} onChange={(e) => upload(e.target.files[0])} className="hidden" />
            </label>
            <button onClick={() => setAdding(false)} className="text-sm text-stone-600">
              {t.cancel}
            </button>
          </div>
        </div>
      )}

      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
      {scans.length > 0 && (
        <ul className="mt-3 divide-y divide-stone-100">
          {scans.map((s) => (
            <li key={s.id}>
              <button onClick={() => view(s)} className="flex w-full items-center gap-3 py-2 text-left">
                <Preview scanId={s.id} className="h-14 w-14 shrink-0 rounded-lg bg-black object-contain" />
                <span className="min-w-0 text-sm">
                  <span className="font-medium text-stone-800">
                    {label(s)}
                    {s.body_part && ` · ${s.body_part.toLowerCase()}`}
                  </span>
                  {s.caption && <span className="block truncate text-stone-600">{s.caption}</span>}
                  <span className="block text-xs text-stone-500">
                    {s.study_date || s.created_at.slice(0, 10)} · {s.uploaded_by_name}, {s.uploaded_by_facility} · {s.size < 1e6 ? `${Math.round(s.size / 1e3)} KB` : `${(s.size / 1e6).toFixed(1)} MB`}
                  </span>
                  {s.burned_in ? <span className="block text-xs font-semibold text-amber-700">⚠️ {t.scanBurnedIn}</span> : null}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {open && (
        <div className="fixed inset-0 z-50 flex flex-col bg-black p-3 text-white">
          <div className="flex items-center justify-between gap-2">
            <p className="text-sm">
              {label(open)} · {open.width}×{open.height}
              {open.frames > 1 && ` · ${t.scanMiddleFrame} (${open.frames})`}
            </p>
            <button onClick={() => setOpen(null)} className="rounded-lg bg-white/15 px-3 py-1 text-sm">
              ✕ {t.close}
            </button>
          </div>
          <div className="flex min-h-0 flex-1 items-center justify-center py-2">
            <Preview scanId={open.id} window={win} className="h-full w-full object-contain" />
          </div>
          {draft && (
            <div className="space-y-2 text-xs">
              {open.modality === "CT" && (
                <div className="flex flex-wrap gap-2">
                  {CT_PRESETS.map((p) => (
                    <button key={p.key} onClick={() => { setDraft(p); setWin(p); }} className="rounded-full bg-white/15 px-3 py-1">
                      {t[p.key]}
                    </button>
                  ))}
                </div>
              )}
              {/* Window/level: centre = which grey value is mid-grey, width = how many values span black to white */}
              <label className="flex items-center gap-2">
                <span className="w-20">{t.scanBrightness}</span>
                <input type="range" min={open.value_min} max={open.value_max} value={draft.center} className="flex-1"
                  onChange={(e) => setDraft({ ...draft, center: Number(e.target.value) })} onPointerUp={() => setWin(draft)} onKeyUp={() => setWin(draft)} />
              </label>
              <label className="flex items-center gap-2">
                <span className="w-20">{t.scanContrast}</span>
                <input type="range" min={1} max={Math.max(range, 2)} value={draft.width} className="flex-1"
                  style={{ direction: "rtl" }} // right = narrower window = more contrast
                  onChange={(e) => setDraft({ ...draft, width: Number(e.target.value) })} onPointerUp={() => setWin(draft)} onKeyUp={() => setWin(draft)} />
              </label>
            </div>
          )}
          <div className="mt-2 flex flex-wrap gap-2 text-sm">
            {draft && (
              <button onClick={() => { setWin(null); setDraft({ center: open.win_center, width: open.win_width }); }} className="rounded-lg bg-white/15 px-3 py-1.5">
                {t.scanReset}
              </button>
            )}
            {canUpload && (
              <button onClick={() => download(open)} className="rounded-lg bg-teal-600 px-3 py-1.5 font-semibold">
                ⬇ {t.scanDownload}
              </button>
            )}
            {open.uploaded_by === userId && (
              <button onClick={() => remove(open)} className="rounded-lg bg-red-600/80 px-3 py-1.5">
                {t.scanDelete}
              </button>
            )}
          </div>
          <p className="mt-2 text-xs text-white/60">{t.scanNotDiagnostic}</p>
        </div>
      )}
    </div>
  );
}
