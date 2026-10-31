import Header from "./Header";

// What each non-CHV role will get, and in which PROSIT week
const PLANS = {
  admin: { week: "Later", text: "Account management: create and disable staff accounts. No routine access to patient data." },
};

export default function RolePlaceholder(props) {
  const { user, t } = props;
  const plan = PLANS[user.role];

  return (
    <div className="min-h-screen bg-stone-50">
      <Header {...props} />
      <main className="mx-auto max-w-2xl px-4 py-16 text-center">
        <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-800">{plan.week}</span>
        <h1 className="mt-4 text-2xl font-bold text-stone-800">{t.comingSoon}</h1>
        <p className="mt-3 text-stone-600">{plan.text}</p>
        <p className="mt-8 text-xs text-stone-400">{t.builtBy}</p>
      </main>
    </div>
  );
}
