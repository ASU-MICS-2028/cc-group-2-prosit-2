import { api } from "./api";

// Checks done without signal wait here until the phone is back online.
// localStorage survives closing the app, so nothing is lost overnight.
const KEY = "hc_pending";
let syncing = false; // stops two syncs running at once and sending a check twice

function readAll() {
  return JSON.parse(localStorage.getItem(KEY) || "[]");
}

export function getPending(userId) {
  // Each CHV only sees (and syncs) their own queued checks on a shared phone
  return readAll().filter((item) => item.userId === userId);
}

export function addPending(item) {
  localStorage.setItem(KEY, JSON.stringify([...readAll(), item]));
}

export async function syncPending(userId) {
  if (syncing) return;
  syncing = true;
  const sent = new Set();
  for (const item of getPending(userId)) {
    try {
      await api(`/patients/${item.patientId}/assess`, { method: "POST", body: item.body });
      sent.add(item.id);
    } catch {
      // still offline or server error: keep it and try again later
    }
  }
  // Re-read so checks added during the sync are not lost
  localStorage.setItem(KEY, JSON.stringify(readAll().filter((item) => !sent.has(item.id))));
  syncing = false;
}
