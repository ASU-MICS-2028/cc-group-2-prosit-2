// Tests run in Node, which has no browser storage: give it a simple in-memory version
function memoryStorage() {
  const items = new Map();
  return {
    getItem: (key) => (items.has(key) ? items.get(key) : null),
    setItem: (key, value) => items.set(key, String(value)),
    removeItem: (key) => items.delete(key),
    clear: () => items.clear(),
  };
}

export function resetBrowser({ keyByte = 7 } = {}) {
  globalThis.sessionStorage = memoryStorage();
  globalThis.localStorage = memoryStorage();
  globalThis.window = { location: { reload() {} } };
  // A fake 32-byte AES key, like the one the server sends at login
  sessionStorage.setItem("hc_key", btoa(String.fromCharCode(...new Uint8Array(32).fill(keyByte))));
  sessionStorage.setItem("hc_token", "test-token");
}
