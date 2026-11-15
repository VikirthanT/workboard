// The ATI block pattern in the top right corner of the sign-in page, drawn as SVG so it needs no image. The blocks sit on one square grid
// with the same slant. Small and faint towards the lower left, they grow and brighten until, at the corner, they fill their cells and
// touch. Their colours are the theme's brand teal and its deep teal, so a dark theme can restyle them.

const CELL = 48;
const COLS = 12;
const ROWS = 9;
const SLANT = 0.28;

interface Block {
  key: string;
  points: string;
  deep: boolean;
  opacity: number;
}

const BLOCKS: Block[] = [];
for (let row = 0; row < ROWS; row += 1) {
  for (let col = 0; col < COLS; col += 1) {
    // 0 at the lower left of the pattern, 1 at the top right corner
    const t = (col / (COLS - 1) + (ROWS - 1 - row) / (ROWS - 1)) / 2;
    if (t < 0.14) continue;
    const u = (t - 0.14) / 0.86;
    const size = CELL * (0.2 + 0.8 * u ** 1.25);
    const slant = size * SLANT;
    const cx = col * CELL + CELL / 2;
    const cy = row * CELL + CELL / 2;
    const half = size / 2;
    const points = [
      [cx - half + slant, cy - half],
      [cx + half, cy - half],
      [cx + half - slant, cy + half],
      [cx - half, cy + half],
    ]
      .map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`)
      .join(' ');
    BLOCKS.push({
      key: `${row}-${col}`,
      points,
      // the faint outer blocks and every other block near the corner are the deep teal, the rest the bright one
      deep: u < 0.45 || ((row + col) % 2 === 1 && u > 0.6),
      opacity: 0.18 + 0.82 * (u * u * (3 - 2 * u)),
    });
  }
}

export function LoginPattern({ className }: { className?: string }) {
  return (
    <svg viewBox={`0 0 ${COLS * CELL} ${ROWS * CELL}`} aria-hidden="true" className={className}>
      {BLOCKS.map((block) => (
        <polygon
          key={block.key}
          points={block.points}
          className={block.deep ? 'fill-brand-ink' : 'fill-brand'}
          fillOpacity={block.opacity.toFixed(2)}
        />
      ))}
    </svg>
  );
}
