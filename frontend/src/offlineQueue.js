import { api } from "./api";
import { encrypt, decrypt } from "./crypto";

// Checks done without signal wait here until the phone is back online.
// localStorage survives closing the app; the health data inside is encrypted.
const KEY = "hc_pending";
let syncing = false; // stops two syncs running at once and sending a check twice

function readAll() {
  return JSON.parse(localStorage.getItem(KEY) || "[]");
}

export function getPending(userId) {
  // Each CHV only sees (and syncs) their own queued checks on a shared phone
  return readAll().filter((item) => item.userId === userId);
}

export async function addPending(userId, check) {
  // Only id and userId stay readable; patient id + vitals are encrypted
  const item = { id: crypto.randomUUID(), userId, enc: await encrypt(check) };
  localStorage.setItem(KEY, JSON.stringify([...readAll(), item]));
}

export async function syncPending(userId) {
  if (syncing) return;
  syncing = true;
  const sent = new Set();
  for (const item of getPending(userId)) {
    try {
      const { patientId, body } = await decrypt(item.enc);
      await api(`/patients/${patientId}/assess`, { method: "POST", body });
      sent.add(item.id);
    } catch {
      // still offline, server error, or no key yet: keep it and try again later
    }
  }
  // Re-read so checks added during the sync are not lost
  localStorage.setItem(KEY, JSON.stringify(readAll().filter((item) => !sent.has(item.id))));
  syncing = false;
}
