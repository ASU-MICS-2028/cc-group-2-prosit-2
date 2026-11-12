// Every backend call goes through here, so the login token is added in one place
export const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

export async function api(path, { method = "GET", body } = {}) {
  const token = sessionStorage.getItem("hc_token");
  const res = await fetch(API_URL + path, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(token && { Authorization: `Bearer ${token}` }),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));

  // Token expired or invalid: clear the session and go back to login
  if (res.status === 401 && token) {
    sessionStorage.clear();
    window.location.reload();
  }
  if (!res.ok) {
    const err = new Error(typeof data.detail === "string" ? data.detail : "Please check the form and try again.");
    err.status = res.status; // e.g. 409 = "are you sure?" (duplicate prescription)
    throw err;
  }
  return data;
}

// Photos and lesson audio come back as bytes, not JSON: fetch with the token and make a
// local URL for <img> or <audio>. On failure, show the server's reason.
export async function apiBlobUrl(path) {
  const token = sessionStorage.getItem("hc_token");
  const res = await fetch(API_URL + path, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(typeof data.detail === "string" ? data.detail : "Could not load this file");
  }
  return URL.createObjectURL(await res.blob());
}
export const apiImageUrl = apiBlobUrl;

// Raw bytes (e.g. an end-to-end encrypted photo, opened on the phone by e2e.js)
export async function apiBytes(path) {
  const token = sessionStorage.getItem("hc_token");
  const res = await fetch(API_URL + path, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  if (!res.ok) throw new Error("Could not load this file");
  return res.arrayBuffer();
}
