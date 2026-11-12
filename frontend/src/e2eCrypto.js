// End-to-end encryption: the locks themselves (Web Crypto API, built into every modern browser).
// No network and no storage here, so every function can be tested on its own (tests/e2eCrypto.test.js).
//
// Three kinds of key:
// 1. My key pair (RSA-OAEP 2048). Public key = an open padlock anyone can use to lock something
//    for me. Private key = the only thing that opens it.
// 2. A password key (PBKDF2, 600,000 rounds of SHA-256 over my password + a random salt). It locks
//    the backup of my private key that the server keeps. The many rounds make guessing slow.
// 3. A patient key (AES-GCM 256, random). It locks that patient's notes and photos.
//    One copy is locked with each care team member's public key.

const PREFIX = "e2e:v1:"; // marks locked text, so old unlocked notes still show as they are
const PBKDF2_ROUNDS = 600_000; // OWASP's current advice for PBKDF2-SHA256
const RSA = { name: "RSA-OAEP", modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: "SHA-256" };
const AES = { name: "AES-GCM", length: 256 };

// ---------- base64 helpers (keys and locked data travel as text) ----------
export function toB64(buffer) {
  const bytes = new Uint8Array(buffer);
  let text = "";
  for (let i = 0; i < bytes.length; i += 0x8000) text += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(text);
}
export const fromB64 = (text) => Uint8Array.from(atob(text), (c) => c.charCodeAt(0));
export const isLocked = (text) => typeof text === "string" && text.startsWith(PREFIX);

// ---------- 1. My key pair ----------
export function makeKeyPair() {
  return crypto.subtle.generateKey(RSA, true, ["wrapKey", "unwrapKey"]);
}
export async function exportPublic(publicKey) {
  return JSON.stringify(await crypto.subtle.exportKey("jwk", publicKey));
}
export function importPublic(text) {
  return crypto.subtle.importKey("jwk", JSON.parse(text), { name: "RSA-OAEP", hash: "SHA-256" }, false, ["wrapKey"]);
}
// The copy kept on the phone cannot be exported, even by code running in the page
export function privateFromBytes(pkcs8) {
  return crypto.subtle.importKey("pkcs8", pkcs8, { name: "RSA-OAEP", hash: "SHA-256" }, false, ["unwrapKey"]);
}

// ---------- 2. Backup of my private key, locked with my password ----------
async function passwordKey(password, salt) {
  const base = await crypto.subtle.importKey("raw", new TextEncoder().encode(password), "PBKDF2", false, ["deriveKey"]);
  return crypto.subtle.deriveKey({ name: "PBKDF2", salt, iterations: PBKDF2_ROUNDS, hash: "SHA-256" }, base, AES, false, [
    "encrypt",
    "decrypt",
  ]);
}
export async function lockBackup(pkcs8, password) {
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const locked = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, await passwordKey(password, salt), pkcs8);
  return { wrapped_private: toB64(locked), salt: toB64(salt), iv: toB64(iv) };
}
// Wrong password -> throws (AES-GCM refuses to open when the key is wrong)
export async function openBackup(backup, password) {
  const key = await passwordKey(password, fromB64(backup.salt));
  return crypto.subtle.decrypt({ name: "AES-GCM", iv: fromB64(backup.iv) }, key, fromB64(backup.wrapped_private));
}
export async function privateToBytes(privateKey) {
  return crypto.subtle.exportKey("pkcs8", privateKey); // only for a brand-new key pair
}

// ---------- 3. Patient keys ----------
export function makePatientKey() {
  return crypto.subtle.generateKey(AES, true, ["encrypt", "decrypt"]);
}
// Lock a patient key for one person, with their public key
export async function lockPatientKey(patientKey, publicKey) {
  return toB64(await crypto.subtle.wrapKey("raw", patientKey, publicKey, { name: "RSA-OAEP" }));
}
// Open my copy with my private key. Extractable, so I can lock copies for new team members
export function openPatientKey(lockedKey, privateKey) {
  return crypto.subtle.unwrapKey("raw", fromB64(lockedKey), privateKey, { name: "RSA-OAEP" }, AES, true, ["encrypt", "decrypt"]);
}

// ---------- Locking notes and photos with a patient key ----------
// AES-GCM: a fresh random 12-byte IV every time, stored in front of the locked bytes.
// GCM also detects tampering: a changed byte makes decrypt fail instead of showing wrong data.
export async function lockBytes(key, bytes) {
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const locked = new Uint8Array(await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, bytes));
  const out = new Uint8Array(12 + locked.length);
  out.set(iv);
  out.set(locked, 12);
  return out;
}
export async function openBytes(key, data) {
  const bytes = new Uint8Array(data);
  return crypto.subtle.decrypt({ name: "AES-GCM", iv: bytes.subarray(0, 12) }, key, bytes.subarray(12));
}
export async function lockText(key, text) {
  return PREFIX + toB64(await lockBytes(key, new TextEncoder().encode(text)));
}
export async function openText(key, text) {
  return new TextDecoder().decode(await openBytes(key, fromB64(text.slice(PREFIX.length))));
}
