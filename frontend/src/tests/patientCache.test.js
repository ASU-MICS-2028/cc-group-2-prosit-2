import { describe, it, expect, beforeEach, vi } from "vitest";
import { cachedApi } from "../patientCache";
import { resetBrowser } from "./setup";

const PATIENTS = [{ id: 1, full_name: "Test Patient A", ref: "HC-0001" }];
const online = () => vi.stubGlobal("fetch", async () => ({ ok: true, status: 200, json: async () => PATIENTS }));
const offline = () => vi.stubGlobal("fetch", async () => { throw new TypeError("Failed to fetch"); });
const waitForSave = () => new Promise((resolve) => setTimeout(resolve, 20));

describe("encrypted patient cache", () => {
  beforeEach(() => resetBrowser());

  it("online: fresh data, and an encrypted copy is saved", async () => {
    online();
    const result = await cachedApi(5, "/patients");
    expect(result).toEqual({ data: PATIENTS, savedAt: null });
    await waitForSave();
    const stored = localStorage.getItem("hc_cache:5:/patients");
    expect(stored).toBeTruthy();
    expect(stored).not.toContain("Test Patient");
  });

  it("offline: returns the saved copy and when it was saved", async () => {
    online();
    await cachedApi(5, "/patients");
    await waitForSave();
    offline();
    const result = await cachedApi(5, "/patients");
    expect(result.data).toEqual(PATIENTS);
    expect(result.savedAt).toBeTruthy();
  });

  it("offline with nothing saved: clear message", async () => {
    offline();
    await expect(cachedApi(5, "/patients/9")).rejects.toThrow(/not been saved/);
  });

  it("another CHV on the same phone gets nothing", async () => {
    online();
    await cachedApi(5, "/patients");
    await waitForSave();
    offline();
    await expect(cachedApi(6, "/patients")).rejects.toThrow(/not been saved/);
  });

  it("a server error is shown, not hidden behind old data", async () => {
    vi.stubGlobal("fetch", async () => ({ ok: false, status: 404, json: async () => ({ detail: "Patient not found" }) }));
    await expect(cachedApi(5, "/patients")).rejects.toThrow("Patient not found");
  });
});
