// End-to-end encryption: connects the locks (e2eCrypto.js) to the server and the phone.
// The server stores only locked keys and locked notes/photos (backend/e2e.py).
import { api, apiBytes } from "./api";
import * as lock from "./e2eCrypto";

export const isLocked = lock.isLocked;
const me = () => JSON.parse(sessionStorage.getItem("hc_user") || "null")?.id;
const patientKeys = new Map(); // patient id -> opened key, in memory only (gone when the tab closes)

// ---------- My private key, kept on this phone in IndexedDB (cannot be exported) ----------
function store(mode, action) {
  return new Promise((resolve, reject) => {
    const open = indexedDB.open("hc_e2e", 1);
    open.onupgradeneeded = () => open.result.createObjectStore("keys");
    open.onerror = () => reject(open.error);
    open.onsuccess = () => {
      const request = action(open.result.transaction("keys", mode).objectStore("keys"));
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    };
  });
}
const savePrivate = (userId, key) => store("readwrite", (s) => s.put(key, `user-${userId}`));
const loadPrivate = (userId) => store("readonly", (s) => s.get(`user-${userId}`));

// After a PASSWORD sign-in: open my key backup (or make my first key pair) and keep it on this phone.
// Fingerprint sign-in has no password, so it uses the copy saved here by an earlier password sign-in.
export async function setupMyKeys(userId, password) {
  let backup = null;
  try {
    backup = await api("/e2e/my-key");
  } catch (err) {
    if (err.status !== 404) throw err;
  }
  if (backup) {
    try {
      await savePrivate(userId, await lock.privateFromBytes(await lock.openBackup(backup, password)));
      return;
    } catch {
      // The backup was locked with an older password (e.g. an admin reset it): make a new key pair.
      // The care team shares this patient's keys again the next time they open the patient.
    }
  }
  const pair = await lock.makeKeyPair();
  const pkcs8 = await lock.privateToBytes(pair.privateKey);
  await api("/e2e/my-key", {
    method: "PUT",
    body: { public_key: await lock.exportPublic(pair.publicKey), ...(await lock.lockBackup(pkcs8, password)), replace: Boolean(backup) },
  });
  await savePrivate(userId, await lock.privateFromBytes(pkcs8));
}

// Password changed: same key pair, backup locked with the new password
export async function rewrapMyKey(oldPassword, newPassword) {
  const backup = await api("/e2e/my-key");
  const pkcs8 = await lock.openBackup(backup, oldPassword);
  await api("/e2e/my-key/rewrap", { method: "POST", body: await lock.lockBackup(pkcs8, newPassword) });
}

export function forgetPatientKeys() {
  patientKeys.clear();
}

// Lock a copy of the patient key for every care team member who does not have one yet
async function shareWithTeam(patientId, key) {
  const missing = await api(`/patients/${patientId}/e2e-missing`);
  if (missing.length === 0) return;
  const grants = await Promise.all(
    missing.map(async (m) => ({ user_id: m.user_id, wrapped_key: await lock.lockPatientKey(key, await lock.importPublic(m.public_key)) })),
  );
  await api(`/patients/${patientId}/e2e-keys`, { method: "POST", body: { grants } });
}

async function makeFirstKey(patientId) {
  const key = await lock.makePatientKey();
  const mine = await api("/e2e/my-key");
  const copy = await lock.lockPatientKey(key, await lock.importPublic(mine.public_key));
  await api(`/patients/${patientId}/e2e-keys`, { method: "POST", body: { grants: [{ user_id: me(), wrapped_key: copy }] } });
  return key;
}

// The opened key for one patient. create: make it if nobody has yet (when writing the first note/photo)
export async function patientKey(patientId, { create = false } = {}) {
  if (patientKeys.has(patientId)) return patientKeys.get(patientId);
  const privateKey = await loadPrivate(me());
  if (!privateKey) throw new Error("Sign in with your password once on this phone to open private notes and photos.");
  let key;
  try {
    key = await lock.openPatientKey((await api(`/patients/${patientId}/e2e-key`)).wrapped_key, privateKey);
  } catch (err) {
    if (!(create && err.status === 404 && err.message === "No key yet")) throw err;
    try {
      key = await makeFirstKey(patientId);
    } catch {
      // Someone else made it at the same moment: use theirs
      key = await lock.openPatientKey((await api(`/patients/${patientId}/e2e-key`)).wrapped_key, privateKey);
    }
  }
  patientKeys.set(patientId, key);
  shareWithTeam(patientId, key).catch(() => {}); // e.g. a nurse at a facility the patient was just referred to
  return key;
}

// Share the key if this phone can (called when a patient is opened or referred). Never fails loudly.
export function shareIfPossible(patientId) {
  return patientKey(patientId).catch(() => {});
}

// ---------- Notes and photos ----------
export async function lockNote(patientId, text) {
  if (!text || !text.trim() || lock.isLocked(text)) return text;
  return lock.lockText(await patientKey(patientId, { create: true }), text);
}
export async function openNote(patientId, text) {
  if (!lock.isLocked(text)) return text; // written before end-to-end encryption
  return lock.openText(await patientKey(patientId), text);
}
export async function lockPhoto(patientId, bytes) {
  return lock.toB64(await lock.lockBytes(await patientKey(patientId, { create: true }), bytes));
}
// Download a locked photo and open it: returns a local picture address for <img>
export async function openPhotoUrl(patientId, photoId) {
  const data = await apiBytes(`/photos/${photoId}`);
  const bytes = await lock.openBytes(await patientKey(patientId), data);
  return URL.createObjectURL(new Blob([bytes], { type: "image/jpeg" }));
}
