import { describe, it, expect } from "vitest";
import { lessonSteps } from "../lessonSteps";

// The slides must say exactly what the reviewed lesson says, nothing added or lost
describe("lesson steps", () => {
  it("makes one step per sentence, keeping every word", () => {
    const body = "Sleep under a net. Is there a fever? Go now!";
    const steps = lessonSteps(body);
    expect(steps.map((s) => s.text)).toEqual(["Sleep under a net.", "Is there a fever?", "Go now!"]);
    expect(steps.map((s) => s.text).join(" ")).toBe(body);
  });

  it("picks a matching picture, or a plain one when unsure", () => {
    expect(lessonSteps("Wash hands with soap.")[0].picture).toBe("🧼");
    expect(lessonSteps("Me da wo ase.")[0].picture).toBe("💡");
  });

  it("copes with an empty lesson", () => {
    expect(lessonSteps("")).toEqual([]);
  });
});
