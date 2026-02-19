import { hashToGrid, avatarColor } from '../utils/bot-utils';

interface IdenticonProps {
  handle: string;
  size?: number;
  dead?: boolean;
}

const Identicon = ({ handle, size = 28, dead = false }: IdenticonProps) => {
  const grid = hashToGrid(handle);
  const color = dead ? '#ff3333' : avatarColor(handle);
  const bgColor = dead ? '#1a0000' : `${color}15`;
  const cellSize = size / 5;

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ borderRadius: '4px' }}>
      <rect width={size} height={size} fill={bgColor} rx={2} />
      {grid.map((on, i) =>
        on ? (
          <rect
            key={i}
            x={(i % 5) * cellSize}
            y={Math.floor(i / 5) * cellSize}
            width={cellSize}
            height={cellSize}
            fill={color}
            opacity={dead ? 0.4 : 0.85}
          />
        ) : null,
      )}
    </svg>
  );
};

export default Identicon;
