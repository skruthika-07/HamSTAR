import { motion, useAnimationControls } from 'framer-motion';
import { Crown } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { useStore } from '../store/useStore';

// The counter can be held back while a result is being revealed, so the new
// Tiara only shows once the little crown has flown over and landed on it.
let held = false;
const listeners = new Set<() => void>();
export const holdTiara = () => {
  held = true;
};
export const releaseTiara = () => {
  held = false;
  listeners.forEach((f) => f());
};

/** Tiara is the only reward currency: one correct question earns one Tiara. */
export function TiaraCounter({ className = '' }: { className?: string }) {
  const tiara = useStore((s) => s.stats.tiara);
  const [shown, setShown] = useState(tiara);
  const [, poke] = useState(0);
  // the counter pulses when the stars land on it
  const pulse = useAnimationControls();
  useEffect(() => {
    const land = () => pulse.start({ scale: [1, 1.28, 0.95, 1], transition: { duration: 0.5 } });
    window.addEventListener('tiara-landed', land);
    return () => window.removeEventListener('tiara-landed', land);
  }, [pulse]);

  useEffect(() => {
    const f = () => poke((n) => n + 1);
    listeners.add(f);
    return () => void listeners.delete(f);
  }, []);

  // Count up (or down, after a reset) instead of jumping.
  useEffect(() => {
    if (held || shown === tiara) return;
    const gap = Math.abs(tiara - shown);
    const stride = Math.max(1, Math.ceil(gap / 12));
    const t = setTimeout(() => setShown(shown + Math.sign(tiara - shown) * Math.min(stride, gap)), gap > 1 ? 40 : 0);
    return () => clearTimeout(t);
  });

  return (
    <motion.span animate={pulse} data-tiara-counter data-tip="Tiara: 1 correct question = 1 Tiara. 500 unlock your certificate." className={`chip bg-gold-soft text-gold-deep ${className}`}>
      <Crown size={14} strokeWidth={2.4} />
      <motion.span key={shown} initial={{ scale: 1.35, y: -2 }} animate={{ scale: 1, y: 0 }} transition={{ type: 'spring', stiffness: 320, damping: 16 }} className="tabular-nums">
        {shown}
      </motion.span>
      Tiara
    </motion.span>
  );
}

const SPARKS = [
  { icon: '⭐', dx: -18, dy: 6, kick: -20 },
  { icon: '🪙', dx: 14, dy: 10, kick: 18 },
  { icon: '⭐', dx: -4, dy: -10, kick: -6 },
  { icon: '🪙', dx: 24, dy: -4, kick: 26 },
  { icon: '⭐', dx: 4, dy: 16, kick: 4 },
];

/** A small crown that appears where it is placed, then flies to the Tiara counter and lets it tick up. */
export function TiaraFlight() {
  const anchor = useRef<HTMLSpanElement>(null);
  const [path, setPath] = useState<{ x: number; y: number; dx: number; dy: number } | null>(null);

  useEffect(() => {
    const from = anchor.current?.getBoundingClientRect();
    const to = document.querySelector('[data-tiara-counter]')?.getBoundingClientRect();
    if (!from || !to || !to.width) {
      releaseTiara();
      return;
    }
    setPath({ x: from.left, y: from.top, dx: to.left + 6 - from.left, dy: to.top - from.top });
    // never leave the counter held if this unmounts mid-flight
    return releaseTiara;
  }, []);

  return (
    <>
      <span ref={anchor} className="inline-block h-6 w-6" aria-hidden />
      {path && (
        <motion.span
          aria-hidden
          className="pointer-events-none fixed z-50 flex h-7 w-7 items-center justify-center rounded-full bg-gold text-ink shadow-md"
          style={{ left: path.x, top: path.y }}
          initial={{ scale: 0, opacity: 0 }}
          animate={{ scale: [0, 1.25, 1, 0.7], opacity: [0, 1, 1, 0], x: [0, 0, path.dx * 0.5, path.dx], y: [0, -14, path.dy * 0.5 - 40, path.dy] }}
          transition={{ duration: 1.05, times: [0, 0.22, 0.6, 1], ease: 'easeInOut' }}
          onAnimationComplete={() => {
            releaseTiara();
            window.dispatchEvent(new Event('tiara-landed'));
          }}
        >
          <Crown size={15} strokeWidth={2.6} />
        </motion.span>
      )}
      {/* a little shower of stars and coins follows the crown up to the counter */}
      {path &&
        SPARKS.map((s, i) => (
          <motion.span
            key={i}
            aria-hidden
            className="pointer-events-none fixed z-50 text-lg leading-none"
            style={{ left: path.x + s.dx, top: path.y + s.dy }}
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: [0, 1.2, 0.9, 0.5], opacity: [0, 1, 1, 0], x: [0, s.kick, (path.dx - s.dx) * 0.5 + s.kick, path.dx - s.dx], y: [0, -24 - i * 4, (path.dy - s.dy) * 0.5 - 50, path.dy - s.dy], rotate: [0, 90, 200, 320] }}
            transition={{ duration: 1.1, delay: 0.08 + i * 0.07, times: [0, 0.2, 0.62, 1], ease: 'easeInOut' }}
          >
            {s.icon}
          </motion.span>
        ))}
    </>
  );
}
