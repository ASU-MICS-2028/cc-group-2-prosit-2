import Logo from "./Logo";

// Opening screen: sits on top of the login page, then fades away to reveal it
export default function Splash() {
  return (
    <div className="hc-splash fixed inset-0 z-50 flex flex-col items-center justify-center bg-teal-700" aria-hidden="true">
      <div className="hc-splash-content flex flex-col items-center">
        <Logo size={88} />
        <p className="mt-6 font-display text-3xl font-semibold text-stone-50">Storm Surfers</p>
      </div>
    </div>
  );
}
