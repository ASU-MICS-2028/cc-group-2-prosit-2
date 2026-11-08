// The brand's signature: a block print of simple shapes, drawn in code (no image to download)
const COLOURS = ["#1f45e0", "#ffc531", "#ff6b4a", "#14c4b2", "#0e2180", "#ff8ad8", "#f6f7fb"];
const SIZE = 100;

// One square: a coloured background with one shape on top
function Tile({ col, row }) {
  const bg = COLOURS[(col * 2 + row * 3) % COLOURS.length];
  const ink = COLOURS[(col * 5 + row + 3) % COLOURS.length === (col * 2 + row * 3) % COLOURS.length ? (col + row + 1) % COLOURS.length : (col * 5 + row + 3) % COLOURS.length];
  const shape = (col * 3 + row * 5) % 4;
  const turn = ((col + row * 2) % 4) * 90;
  return (
    <g transform={`translate(${col * SIZE} ${row * SIZE})`}>
      <rect width={SIZE} height={SIZE} fill={bg} />
      <g transform={`rotate(${turn} 50 50)`} fill={ink}>
        {shape === 0 && <circle cx="50" cy="50" r="34" />}
        {shape === 1 && <path d="M0 0H100A100 100 0 0 1 0 100Z" />}
        {shape === 2 && <path d="M0 50A50 50 0 0 1 100 50Z" />}
        {shape === 3 && <path d="M50 0 100 50 50 100 0 50Z" />}
      </g>
    </g>
  );
}

export default function Pattern({ cols = 8, rows = 6 }) {
  const tiles = [];
  for (let row = 0; row < rows; row++) for (let col = 0; col < cols; col++) tiles.push(<Tile key={`${col}-${row}`} col={col} row={row} />);
  return (
    <svg viewBox={`0 0 ${cols * SIZE} ${rows * SIZE}`} preserveAspectRatio="xMidYMid slice" className="block h-full w-full" aria-hidden="true">
      {tiles}
    </svg>
  );
}
