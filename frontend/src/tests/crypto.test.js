import { describe, it, expect, beforeEach } from "vitest";
import { encrypt, decrypt } from "../crypto";
import { resetBrowser } from "./setup";

// AES-256-GCM: hides the data AND detects tampering
describe("offline encryption", () => {
  beforeEach(() => resetBrowser());

  it("decrypts back to the same data", async () => {
    const check = { patient: "Test Patient A", systolic_bp: 150 };
    expect(await decrypt(await encrypt(check))).toEqual(check);
  });

  it("stores no readable health data", async () => {
    const stored = JSON.stringify(await encrypt({ patient: "Test Patient A" }));
    expect(stored).not.toContain("Test Patient");
  });

  it("uses a new random IV every time", async () => {
    const a = await encrypt({ x: 1 });
    const b = await encrypt({ x: 1 });
    expect(a.iv).not.toBe(b.iv);
    expect(a.data).not.toBe(b.data);
  });

  it("rejects tampered data", async () => {
    const enc = await encrypt({ systolic_bp: 150 });
    const bytes = Uint8Array.from(atob(enc.data), (c) => c.charCodeAt(0));
    bytes[0] ^= 1; // change one bit
    await expect(decrypt({ ...enc, data: btoa(String.fromCharCode(...bytes)) })).rejects.toThrow();
  });

  it("cannot be read with another user's key", async () => {
    const enc = await encrypt({ systolic_bp: 150 });
    resetBrowser({ keyByte: 9 });
    await expect(decrypt(enc)).rejects.toThrow();
  });

  it("needs a login (no key = no access)", async () => {
    sessionStorage.removeItem("hc_key");
    await expect(encrypt({ x: 1 })).rejects.toThrow(/log in/);
  });
});
