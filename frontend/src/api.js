// Every backend call goes through here, so the login token is added in one place
const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

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
    throw new Error(typeof data.detail === "string" ? data.detail : "Please check the form and try again.");
  }
  return data;
}
