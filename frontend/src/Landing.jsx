import Logo from "./Logo";

const JOURNEY = [
  ["Volunteer", "A community health volunteer registers the patient with consent and records vitals. The risk check works with no signal."],
  ["Health centre", "High-risk cases reach the nearest nurse or midwife as a referral, ordered by urgency."],
  ["Specialist", "A doctor reviews the case, joins a low-bandwidth video call and sends a prescription to the pharmacy."],
  ["Public health", "GHS officers see anonymised district totals and outbreak alerts. Never a patient's name."],
];

const FACTS = [
  ["1 : 10,000", "doctors to people in Ghana. WHO recommends 1 : 1,000."],
  ["40%", "of Ghanaians live more than 5 km from a health facility."],
  ["83%", "of Ghanaians own a mobile phone."],
  ["15,000+", "community health volunteers need better tools."],
];

const FEATURES = [
  ["Works offline", "Encrypted records stay on the phone and sync when signal returns."],
  ["Five languages", "English, Twi, Ewe, Ga and Dagbani."],
  ["Telemedicine", "Video consultations, appointments and digital prescriptions."],
  ["Outbreak watch", "District map, weekly trends and early warnings."],
  ["Community insurance", "Premiums paid by mobile money."],
  ["Worker training", "Clinician-reviewed courses, quizzes and certificates."],
];

const TEAM = ["Alice Iris Kare Acquah", "Henry Kofi Brandoh", "Clifford Yeboah", "Isaac Ansah Amoah"];

export default function Landing({ onSignIn }) {
  const signIn = (
    <button onClick={onSignIn} className="bg-marigold px-6 py-3 font-semibold text-teal-900 hover:brightness-105">
      Sign in
    </button>
  );

  return (
    <div className="bg-stone-50 text-stone-800">
      <section className="relative overflow-hidden bg-teal-900 text-stone-50">
        <nav className="mx-auto flex max-w-6xl items-center justify-between px-5 py-5">
          <Logo size={38} />
          <button onClick={onSignIn} className="border border-teal-300 px-4 py-1.5 text-sm font-medium hover:bg-teal-800">Sign in</button>
        </nav>

        <div className="mx-auto max-w-6xl px-5 pb-10 pt-10 sm:pt-16">
          <p className="text-sm font-medium text-teal-200">Community health for rural Ghana</p>
          <h1 className="mt-3 font-display text-[clamp(3.1rem,12.5vw,9.5rem)] font-extrabold leading-[0.92]">HealthConnect</h1>
          <p className="mt-3 font-display text-2xl font-semibold text-marigold sm:text-4xl">by Storm Surfers</p>
          <p className="mt-7 max-w-xl text-lg text-teal-50">
            From a volunteer's phone in the village to a specialist in the city, every patient stays connected to care, even where the network stops.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-5">
            {signIn}
            <a href="#journey" className="font-medium underline underline-offset-4">See how it works</a>
          </div>
        </div>

        <svg viewBox="0 0 1200 120" className="block h-24 w-full sm:h-32" preserveAspectRatio="none" aria-hidden="true">
          <path
            className="hc-draw"
            vectorEffect="non-scaling-stroke"
            d="M0 80H300l24-60 36 100 30-70 18 30H690l24-60 36 100 30-70 18 30H1200"
            fill="none"
            stroke="#f0ae2b"
            strokeWidth="3"
          />
        </svg>
        <div className="hc-band" />
      </section>

      <section id="journey" className="mx-auto max-w-6xl px-5 py-20">
        <h2 className="max-w-2xl text-4xl font-bold leading-tight sm:text-5xl">One patient. One connected journey.</h2>
        <ol className="mt-12 grid gap-10 md:grid-cols-4">
          {JOURNEY.map(([title, body], i) => (
            <li key={title} className="border-t-2 border-teal-800 pt-4">
              <p className="font-display text-5xl font-bold text-marigold">{i + 1}</p>
              <h3 className="mt-3 text-lg font-bold">{title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-stone-600">{body}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="bg-stone-100">
        <div className="mx-auto max-w-6xl px-5 py-20">
          <h2 className="text-3xl font-bold sm:text-4xl">Why this matters</h2>
          <dl className="mt-10 grid gap-x-10 gap-y-8 sm:grid-cols-2">
            {FACTS.map(([value, label]) => (
              <div key={value}>
                <dt className="font-display text-5xl font-bold text-teal-800 sm:text-6xl">{value}</dt>
                <dd className="mt-1 text-stone-600">{label}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-8 text-xs text-stone-500">Figures as given in the ICS 534 project brief.</p>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-5 py-20">
        <h2 className="text-3xl font-bold sm:text-4xl">Built for the whole health system</h2>
        <div className="mt-8 grid border-t border-stone-300 sm:grid-cols-2">
          {FEATURES.map(([title, body]) => (
            <div key={title} className="flex flex-col gap-1 border-b border-stone-300 py-5 sm:pr-10">
              <h3 className="text-lg font-bold">{title}</h3>
              <p className="text-sm text-stone-600">{body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="bg-teal-900 text-stone-50">
        <div className="hc-band" />
        <div className="mx-auto flex max-w-6xl flex-col items-start gap-6 px-5 py-14 md:flex-row md:items-center md:justify-between">
          <div className="max-w-2xl">
            <h2 className="text-3xl font-bold">A student prototype, honestly labelled.</h2>
            <p className="mt-3 text-teal-100">
              HealthConnect uses fake test patients only, and is not connected to real GHS, NHIS or hospital systems.
            </p>
          </div>
          {signIn}
        </div>
        <footer className="mx-auto max-w-6xl border-t border-teal-800 px-5 py-6 text-sm text-teal-200">
          <p className="font-semibold text-white">Storm Surfers · ICS 534 Group 2</p>
          <p className="mt-1">{TEAM.join(" · ")}</p>
        </footer>
      </section>
    </div>
  );
}
