// A lesson plays as one picture per sentence, so the slides never say more than the reviewed text.
// Pictures come from English keywords; any other language gets the plain light bulb.
const PICTURES = [
  [/rehydration/i, "🥤"],
  [/remed|herb/i, "🌿"],
  [/mosquito|net\b|sleep/i, "🛏️"],
  [/soap|wash/i, "🧼"],
  [/water|drink/i, "💧"],
  [/antenatal|baby|pregnan/i, "🤰"],
  [/fever|tested/i, "🌡️"],
  [/facility|clinic|nurse|doctor/i, "🏥"],
];

export function lessonSteps(body) {
  const sentences = body.match(/[^.!?]+[.!?]*/g) || [];
  return sentences
    .map((text) => text.trim())
    .filter(Boolean)
    .map((text) => ({ text, picture: PICTURES.find(([pattern]) => pattern.test(text))?.[1] || "💡" }));
}
