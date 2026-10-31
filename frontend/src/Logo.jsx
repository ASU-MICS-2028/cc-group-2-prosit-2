// Heart with a pulse line: health + connection
export default function Logo({ size = 40 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" aria-hidden="true">
      <rect width="48" height="48" rx="12" fill="#0f766e" />
      <path
        d="M24 37s-12-7.4-12-16a7 7 0 0 1 12-4.9A7 7 0 0 1 36 21c0 8.6-12 16-12 16z"
        fill="#fbbf24"
      />
      <path
        d="M13 24h6l2-4 4 8 2-4h8"
        fill="none"
        stroke="#0f766e"
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
