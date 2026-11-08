import Logo from "./Logo";
import Icon from "./Icon";

// The people and places that HealthConnect joins up
const NODES = [
  { x: -140, y: -62, colour: "#7cd5a0", icon: "patients" },
  { x: 140, y: -62, colour: "#8cc4f5", icon: "doctor" },
  { x: -150, y: 44, colour: "#ffb84d", icon: "nurse" },
  { x: 150, y: 44, colour: "#b79cf2", icon: "centre" },
  { x: -72, y: 92, colour: "#f59a8f", icon: "equipment" },
  { x: 72, y: 92, colour: "#6fd3d6", icon: "pill" },
];

// Opening: the network connects, the name fades to Storm Surfers, then the login page appears.
// It sits on top of the login page. A tap skips it.
export default function Splash({ onSkip }) {
  return (
    <div onClick={onSkip} className="hc-splash fixed inset-0 z-50 bg-white" aria-hidden="true">
      <div className="hc-stage-1 absolute inset-0 flex flex-col items-center justify-center px-4">
        <div className="relative w-full max-w-md">
          <svg viewBox="-180 -125 360 250" className="block w-full">
            <circle className="hc-ring" r="36" fill="none" stroke="#7cd5a0" strokeWidth="2" />
            {NODES.map((n, i) => (
              <g key={i}>
                <line className="hc-link" style={{ animationDelay: `${0.2 + i * 0.16}s` }} x2={n.x} y2={n.y} pathLength="1" stroke="#aee6c3" strokeWidth="2.5" strokeLinecap="round" />
                <line className="hc-pulse" style={{ animationDelay: `${1 + i * 0.16}s` }} x2={n.x} y2={n.y} pathLength="1" stroke="#16924b" strokeWidth="4" strokeLinecap="round" />
                <g className="hc-node" style={{ animationDelay: `${0.65 + i * 0.16}s`, color: "#222b29" }}>
                  <circle className="hc-colour" style={{ animationDelay: `${-i * 0.5}s` }} cx={n.x} cy={n.y} r="21" fill={n.colour} />
                  <g transform={`translate(${n.x - 12} ${n.y - 12})`}><Icon name={n.icon} size={24} /></g>
                </g>
              </g>
            ))}
          </svg>
          <div className="absolute inset-0 flex items-center justify-center"><Logo size={64} /></div>
        </div>
        <p className="hc-name mt-4 font-display text-5xl font-extrabold text-stone-800 sm:text-6xl">HealthConnect</p>
      </div>
      <div className="hc-stage-2 absolute inset-0 flex flex-col items-center justify-center px-4 text-center">
        <p className="font-serif text-2xl italic text-stone-600 sm:text-3xl">Developed by</p>
        <p className="mt-1 font-display text-6xl font-extrabold text-teal-700 sm:text-7xl">Storm Surfers</p>
        <p className="mt-5 text-xs font-semibold uppercase tracking-[0.3em] text-stone-500 sm:text-sm">Cloud Computing Prosit 2</p>
      </div>
    </div>
  );
}
