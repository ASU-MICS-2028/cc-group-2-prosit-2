// Lists English keys that each language has not translated yet.
// Run: node scripts/check-i18n.mjs   (exits 1 if a language has a typo'd key)
import { readFileSync } from "node:fs";

// Kept in English on purpose: names, medical terms without an everyday word, and
// the admin screen (used by system administrators, not health workers)
const SAME_AS_ENGLISH = {
  tw: ["appName", "chvLabel", "role_chv", "short_meningitis", "short_pneumonia", "cond_meningitis", "cond_pneumonia"],
  ee: ["appName", "chvLabel", "role_chv", "short_meningitis", "short_pneumonia", "short_measles", "cond_meningitis", "cond_pneumonia", "cond_measles"],
  ha: ["appName", "chvLabel", "role_chv"],
  dag: ["appName", "chvLabel", "role_chv"],
};

const src = readFileSync(new URL("../src/i18n.js", import.meta.url), "utf8");
const blocks = {};
for (const m of src.matchAll(/^ {2}(\w+): \{([\s\S]*?)^ {2}\},?$|^ {2}(\w+): \{\},?$/gm)) {
  const code = m[1] || m[3];
  blocks[code] = [...(m[2] || "").matchAll(/^\s+(\w+):/gm)].map((k) => k[1]);
}
const en = blocks.en;
let typos = false;
for (const [code, keys] of Object.entries(blocks)) {
  if (code === "en") continue;
  const have = new Set(keys);
  const missing = en.filter((k) => !have.has(k) && !k.startsWith("admin") && !(SAME_AS_ENGLISH[code] || []).includes(k));
  const extra = keys.filter((k) => !en.includes(k));
  console.log(`${code}: ${have.size}/${en.length} translated${missing.length ? `, ${missing.length} missing` : ""}`);
  if (missing.length && missing.length < 20) console.log("   missing:", missing.join(", "));
  if (extra.length) (typos = true), console.log("   not in English (typo?):", extra.join(", "));
}
process.exit(typos ? 1 : 0);
