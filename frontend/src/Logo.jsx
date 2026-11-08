// The letter H, with a heartbeat as its crossbar: health + connection
export default function Logo({ size = 40 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" aria-hidden="true">
      <rect width="48" height="48" rx="9" fill="#f0ae2b" />
      <path d="M12 10v28M36 10v28" stroke="#11452e" strokeWidth="5" strokeLinecap="round" />
      <path d="M12 24h7l3-7 4 14 3-7h7" fill="none" stroke="#11452e" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
