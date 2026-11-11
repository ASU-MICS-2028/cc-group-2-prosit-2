import { useState, useEffect } from "react";
import { api, apiImageUrl } from "./api";
import { inputClass } from "./styles";

const KINDS = ["wound", "skin", "xray", "lab", "other"];
const MAX_SIDE = 1280; // pixels: enough to see a wound or read an X-ray, small enough for 2G
const MAX_BYTES = 380_000;

const SLOW_MAX_SIDE = 800; // on 2G: about a third of the bytes, still clear enough for a wound or rash

// Android phones say when they are on 2G (Network Information API). Our 2G test: a 1280 px
// photo took about 105 s on GPRS, so on 2G we send a smaller one. Other phones: normal size.
function onSlowNetwork() {
  return ["slow-2g", "2g"].includes(navigator.connection?.effectiveType);
}

// Shrink a camera photo on the phone before sending: draw it smaller, save as JPEG
async function shrink(file) {
  const bitmap = await createImageBitmap(file);
  const maxSide = onSlowNetwork() ? SLOW_MAX_SIDE : MAX_SIDE;
  const scale = Math.min(1, maxSide / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  canvas.getContext("2d").drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  for (const quality of [0.75, 0.6, 0.45]) {
    const url = canvas.toDataURL("image/jpeg", quality);
    if (url.length * 0.75 < MAX_BYTES) return url; // base64 is 4/3 the size of the bytes
  }
  throw new Error("Photo too large");
}

function Thumb({ photo, onOpen }) {
  const [src, setSrc] = useState(null);
  useEffect(() => {
    let url;
    apiImageUrl(`/photos/${photo.id}`).then((u) => setSrc((url = u))).catch(() => {});
    return () => url && URL.revokeObjectURL(url); // free the memory when the photo leaves the screen
  }, [photo.id]);
  return (
    <button onClick={() => src && onOpen(src, photo)} className="overflow-hidden rounded-xl border border-stone-200 bg-stone-100 text-left">
      {src ? <img src={src} alt={photo.caption || photo.kind} className="h-24 w-full object-cover" /> : <div className="h-24 w-full animate-pulse" />}
    </button>
  );
}

// Patient photos: CHV patient page, and nurse/doctor patient history. Shared along the referral chain.
export default function PhotosPanel({ t, patientId, userId }) {
  const [photos, setPhotos] = useState([]);
  const [adding, setAdding] = useState(false);
  const [kind, setKind] = useState("wound");
  const [caption, setCaption] = useState("");
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [open, setOpen] = useState(null); // { src, photo } shown large

  const load = () => api(`/patients/${patientId}/photos`).then(setPhotos).catch((err) => setError(err.message));
  useEffect(() => {
    load();
  }, [patientId]); // eslint-disable-line react-hooks/exhaustive-deps

  const upload = async (file) => {
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      const image = await shrink(file);
      await api(`/patients/${patientId}/photos`, { method: "POST", body: { kind, caption, consent, image } });
      setAdding(false);
      setCaption("");
      setConsent(false);
      load();
    } catch (err) {
      setError(err.message);
    }
    setBusy(false);
  };
  const remove = async (photo) => {
    if (!window.confirm(t.photoDeleteConfirm)) return;
    await api(`/photos/${photo.id}`, { method: "DELETE" }).catch((err) => setError(err.message));
    setOpen(null);
    load();
  };

  return (
    <div className="mt-4 rounded-2xl border border-stone-200 bg-white p-4">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold text-stone-800">📷 {t.photosTitle} ({photos.length})</h2>
        {!adding && (
          <button onClick={() => setAdding(true)} className="text-sm font-semibold text-teal-700 hover:underline">
            + {t.photoAdd}
          </button>
        )}
      </div>
      <p className="text-xs text-stone-500">{t.photosHint}</p>

      {adding && (
        <div className="mt-3 space-y-2 rounded-xl bg-teal-50/60 p-3">
          <div className="grid grid-cols-2 gap-2">
            <select value={kind} onChange={(e) => setKind(e.target.value)} className={inputClass}>
              {KINDS.map((k) => (
                <option key={k} value={k}>
                  {t["photo_" + k]}
                </option>
              ))}
            </select>
            <input value={caption} onChange={(e) => setCaption(e.target.value)} maxLength={200} placeholder={t.photoCaption} className={inputClass} />
          </div>
          <label className="flex items-start gap-2 text-sm text-stone-700">
            <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} className="mt-1" />
            <span>{t.photoConsent}</span>
          </label>
          <div className="flex items-center gap-2">
            <label className={`rounded-xl px-4 py-2 text-sm font-semibold text-white ${consent && !busy ? "cursor-pointer bg-teal-700 hover:bg-teal-800" : "bg-teal-700/40"}`}>
              {busy ? t.photoUploading : `📷 ${t.photoTake}`}
              {/* capture opens the back camera on a phone; on a laptop it opens a file picker */}
              <input type="file" accept="image/*" capture="environment" disabled={!consent || busy} onChange={(e) => upload(e.target.files[0])} className="hidden" />
            </label>
            <button onClick={() => setAdding(false)} className="text-sm text-stone-600">
              {t.cancel}
            </button>
          </div>
        </div>
      )}

      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
      {photos.length > 0 && (
        <div className="mt-3 grid grid-cols-3 gap-2 sm:grid-cols-4">
          {photos.map((p) => (
            <div key={p.id}>
              <Thumb photo={p} onOpen={(src, photo) => setOpen({ src, photo })} />
              <p className="mt-0.5 truncate text-xs text-stone-600">{t["photo_" + p.kind]}</p>
            </div>
          ))}
        </div>
      )}

      {open && (
        <div onClick={() => setOpen(null)} className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-black/80 p-4">
          <img src={open.src} alt={open.photo.caption || open.photo.kind} className="max-h-[75vh] max-w-full rounded-lg" />
          <div onClick={(e) => e.stopPropagation()} className="mt-3 max-w-lg rounded-xl bg-white p-3 text-sm text-stone-700">
            <p className="font-semibold">
              {t["photo_" + open.photo.kind]}
              {open.photo.caption && `: ${open.photo.caption}`}
            </p>
            <p className="text-xs text-stone-500">
              {open.photo.uploaded_by_name} ({open.photo.uploaded_by_facility || open.photo.uploaded_by_role}) · {open.photo.created_at}
            </p>
            <div className="mt-2 flex gap-3">
              <button onClick={() => setOpen(null)} className="font-semibold text-teal-700">
                {t.close}
              </button>
              {open.photo.uploaded_by === userId && (
                <button onClick={() => remove(open.photo)} className="text-red-600">
                  {t.photoDelete}
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
