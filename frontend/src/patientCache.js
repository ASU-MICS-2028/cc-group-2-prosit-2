import { api } from "./api";
import { encrypt, decrypt } from "./crypto";

// Encrypted copies of what the CHV last saw (patient list, patient pages),
// so they can still be opened with no signal, even after a page reload.
// Stored per user: another CHV on the same phone has a different key and cannot read them.
const keyFor = (userId, path) => `hc_cache:${userId}:${path}`;

export async function cachedApi(userId, path) {
  try {
    const data = await api(path);
    // Online: save an encrypted copy for later (a failed save must not break the screen)
    encrypt({ data, savedAt: new Date().toISOString() })
      .then((enc) => localStorage.setItem(keyFor(userId, path), JSON.stringify(enc)))
      .catch(() => {});
    return { data, savedAt: null };
  } catch (err) {
    // TypeError = the request never reached the server (no signal). Anything else is a real error.
    if (!(err instanceof TypeError)) throw err;
    const saved = localStorage.getItem(keyFor(userId, path));
    if (!saved) throw new Error("No signal, and this page has not been saved on the phone yet.");
    return decrypt(JSON.parse(saved)); // { data, savedAt }
  }
}
