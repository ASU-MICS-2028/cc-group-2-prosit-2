// AES-GCM encryption for data kept on the phone (Web Crypto API, built into browsers).
// The key comes from the server at login and lives in sessionStorage only.

const toB64 = (bytes) => btoa(String.fromCharCode(...new Uint8Array(bytes)));
const fromB64 = (text) => Uint8Array.from(atob(text), (c) => c.charCodeAt(0));

async function getKey() {
  const raw = sessionStorage.getItem("hc_key");
  if (!raw) throw new Error("No encryption key. Please log in again.");
  return crypto.subtle.importKey("raw", fromB64(raw), "AES-GCM", false, ["encrypt", "decrypt"]);
}

export async function encrypt(obj) {
  const iv = crypto.getRandomValues(new Uint8Array(12)); // new random IV every time
  const data = await crypto.subtle.encrypt(
    { name: "AES-GCM", iv },
    await getKey(),
    new TextEncoder().encode(JSON.stringify(obj))
  );
  return { iv: toB64(iv), data: toB64(data) };
}

export async function decrypt({ iv, data }) {
  // Throws if the key is wrong or the data was tampered with
  const plain = await crypto.subtle.decrypt({ name: "AES-GCM", iv: fromB64(iv) }, await getKey(), fromB64(data));
  return JSON.parse(new TextDecoder().decode(plain));
}
