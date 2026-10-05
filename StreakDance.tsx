import { motion } from 'framer-motion';
import { ArrowRight } from 'lucide-react';
import { useEffect } from 'react';
import { createPortal } from 'react-dom';
import { HamstarMascot } from './mascot/HamstarMascot';

/** Correct answers in a row that earn a happy dance. */
export const STREAK_MILESTONES = [3, 5, 10];

const LINES: Record<number, string> = {
  3: "3 in a row! You're warming up, Brainy Hamster!",
  5: "5 in a row! You're on fire, Brainy Hamster!",
  10: "10 in a row! Unstoppable, Brainy Hamster!",
};

/** The hamster's happy dance for a streak milestone. Goes away by itself after two seconds, or with Keep Going. */
export function StreakDance({ streak, onDone }: { streak: number; onDone: () => void }) {
  useEffect(() => {
    const t = setTimeout(onDone, 2000);
    return () => clearTimeout(t);
  }, [onDone]);

  return createPortal(
    <motion.div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/35 p-4" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} role="status" aria-live="polite" onClick={onDone}>
      <motion.div
        initial={{ scale: 0.7, y: 30 }}
        animate={{ scale: 1, y: 0 }}
        transition={{ type: 'spring', stiffness: 280, damping: 18 }}
        className="w-full max-w-sm rounded-[2rem] border-2 border-[#ecd596] bg-[#fff6d8] px-7 pb-7 pt-5 text-center shadow-[0_24px_60px_-18px_rgba(70,41,27,0.55)]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* the happy dance: hop, wiggle, and a little spin */}
        <motion.div
          className="mx-auto w-fit"
          animate={{ y: [0, -26, 0, -18, 0], rotate: [0, -12, 12, -8, 360], scale: [1, 1.05, 1, 1.05, 1] }}
          transition={{ duration: 1.6, repeat: Infinity, ease: 'easeInOut', times: [0, 0.2, 0.45, 0.65, 1] }}
        >
          <HamstarMascot state="celebrating" size={150} />
        </motion.div>
        <div className="mt-1 text-4xl" aria-hidden>
          🔥
        </div>
        <h2 className="font-display mt-1 text-2xl leading-tight text-[#46291b]">{LINES[streak] ?? `${streak} in a row! You're on fire, Brainy Hamster!`}</h2>
        <button className="btn btn-primary mt-5 w-full" autoFocus onClick={onDone}>
          Keep Going! <ArrowRight size={18} />
        </button>
      </motion.div>
    </motion.div>,
    document.body,
  );
}
