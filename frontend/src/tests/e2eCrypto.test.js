import { describe, it, expect } from "vitest";
import * as e2e from "../e2eCrypto";

// End-to-end encryption, with real Web Crypto keys
describe("end-to-end encryption", () => {
  it("a note locked for the team opens only with a team member's private key", async () => {
    const chv = await e2e.makeKeyPair();
    const nurse = await e2e.makeKeyPair();
    const outsider = await e2e.makeKeyPair();

    // The CHV makes the patient key and locks a copy for herself and for the nurse
    const patientKey = await e2e.makePatientKey();
    const forNurse = await e2e.lockPatientKey(patientKey, await e2e.importPublic(await e2e.exportPublic(nurse.publicKey)));
    const note = await e2e.lockText(patientKey, "Wound on left leg, smells bad. Mother worried.");
    expect(e2e.isLocked(note)).toBe(true);
    expect(note).not.toContain("Wound");

    // The nurse opens her copy and reads the note
    const nurseKey = await e2e.openPatientKey(forNurse, nurse.privateKey);
    expect(await e2e.openText(nurseKey, note)).toBe("Wound on left leg, smells bad. Mother worried.");

    // The CHV's own copy works too; someone else's private key cannot open the nurse's copy
    const forChv = await e2e.lockPatientKey(patientKey, chv.publicKey);
    expect(await e2e.openText(await e2e.openPatientKey(forChv, chv.privateKey), note)).toContain("Mother worried");
    await expect(e2e.openPatientKey(forNurse, outsider.privateKey)).rejects.toThrow();
  });

  it("detects a changed note instead of showing wrong text", async () => {
    const key = await e2e.makePatientKey();
    const note = await e2e.lockText(key, "BP 150/100");
    const bytes = e2e.fromB64(note.slice(7));
    bytes[20] ^= 1; // flip one bit
    await expect(e2e.openText(key, "e2e:v1:" + e2e.toB64(bytes))).rejects.toThrow();
  });

  it("the private key backup opens only with the right password", async () => {
    const pair = await e2e.makeKeyPair();
    const backup = await e2e.lockBackup(await e2e.privateToBytes(pair.privateKey), "Correct horse 1!");
    const restored = await e2e.privateFromBytes(await e2e.openBackup(backup, "Correct horse 1!"));
    await expect(e2e.openBackup(backup, "wrong password")).rejects.toThrow();

    // The restored key opens a patient key locked with the original public key, and cannot be exported
    const patientKey = await e2e.makePatientKey();
    const copy = await e2e.lockPatientKey(patientKey, pair.publicKey);
    const opened = await e2e.openPatientKey(copy, restored);
    expect(await e2e.openText(opened, await e2e.lockText(patientKey, "ok"))).toBe("ok");
    await expect(crypto.subtle.exportKey("pkcs8", restored)).rejects.toThrow();
  }, 20000);

  it("photos: the same picture locked twice looks different (fresh IV)", async () => {
    const key = await e2e.makePatientKey();
    const photo = crypto.getRandomValues(new Uint8Array(2000));
    const a = await e2e.lockBytes(key, photo);
    const b = await e2e.lockBytes(key, photo);
    expect(e2e.toB64(a)).not.toBe(e2e.toB64(b));
    expect(new Uint8Array(await e2e.openBytes(key, a))).toEqual(photo);
  });
});
