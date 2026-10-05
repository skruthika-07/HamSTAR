import type { CSSProperties } from 'react';

// Fixed, hand-picked positions so the dust does not jump between renders.
const MOTES = [
  [8, 22, 5, 17, 0],
  [17, 64, 3, 23, 4],
  [27, 12, 4, 19, 9],
  [36, 80, 3, 26, 2],
  [48, 6, 5, 21, 12],
  [58, 90, 3, 24, 6],
  [69, 16, 4, 18, 15],
  [78, 72, 5, 27, 8],
  [88, 30, 3, 20, 3],
  [94, 86, 4, 25, 11],
];

/** Barely-there life in the room: a slow drift of sunlight and a few motes of dust in it. Sits behind the sheets. */
export function Ambient() {
  return (
    <div className="ambient" aria-hidden>
      <div className="sunbeam" />
      {MOTES.map(([x, y, size, dur, delay], i) => (
        <span key={i} className="mote" style={{ left: `${x}%`, top: `${y}%`, width: size, height: size, animationDuration: `${dur}s`, animationDelay: `-${delay}s` } as CSSProperties} />
      ))}
    </div>
  );
}
