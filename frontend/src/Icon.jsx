// Simple line icons for the menu. Inline drawings, so they cost no extra download.
const PATHS = {
  doctor: "M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8M4 21v-2a6 6 0 0 1 6-5h4a6 6 0 0 1 6 5v2M12 15.5v4M10 17.5h4",
  nurse: "M8 7V4.5L12 3l4 1.5V7zM8 7v2a4 4 0 0 0 8 0V7M4 21v-1a6 6 0 0 1 6-5h4a6 6 0 0 1 6 5v1",
  patients: "M16 20v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 10a4 4 0 1 0 0-8 4 4 0 0 0 0 8M22 20v-2a4 4 0 0 0-3-3.8M16 2.2a4 4 0 0 1 0 7.6",
  referrals: "M3 13h5l2 3h4l2-3h5M5 4h14l2 9v6a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-6z",
  calendar: "M4 5h16a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1M3 10h18M8 3v4M16 3v4",
  centre: "M4 21V5a1 1 0 0 1 1-1h14a1 1 0 0 1 1 1v16M2 21h20M12 8v6M9 11h6M10 21v-3h4v3",
  equipment: "M6 3v6a4 4 0 0 0 8 0V3M10 13v3a5 5 0 0 0 10 0v-2M20 14a2 2 0 1 0 0-4 2 2 0 0 0 0 4",
  lessons: "M12 6c-2-2-5-2-9-2v15c4 0 7 0 9 2 2-2 5-2 9-2V4c-4 0-7 0-9 2zM12 6v15",
  training: "M12 15a6 6 0 1 0 0-12 6 6 0 0 0 0 12M8.5 14 7 22l5-3 5 3-1.5-8",
  pill: "m10.5 20.5 10-10a5 5 0 0 0-7-7l-10 10a5 5 0 0 0 7 7M8.5 8.5l7 7",
  stock: "M21 8 12 3 3 8v8l9 5 9-5zM3 8l9 5 9-5M12 13v8",
  history: "M3 12a9 9 0 1 0 3-6.7L3 8M3 3v5h5M12 7v5l4 2",
  overview: "M3 12h4l3 8 4-16 3 8h4",
  map: "M9 4 3 6v14l6-2 6 2 6-2V4l-6 2zM9 4v14M15 6v14",
  impact: "M4 20V10M10 20V4M16 20v-7M22 20H2",
  accounts: "M12 3 4 6v6c0 5 3.4 8 8 9 4.6-1 8-4 8-9V6zM9 12l2 2 4-4",
  system: "M4 4h16v6H4zM4 14h16v6H4zM8 7h.01M8 17h.01",
};

export default function Icon({ name, size = 20 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={PATHS[name]} />
    </svg>
  );
}
