import { motion } from 'framer-motion';
import { ArrowRight } from 'lucide-react';
import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { confettiBurst } from '../lib/celebrate';

const EMOJI = ['🌟', '🐹', '🎉'];

interface Props {
  message: string;
  /** A small note under the subtext, e.g. progress towards a badge. */
  note?: string;
  onContinue: () => void;
}

/** The flashcard shown in the middle of the screen once a mistake has been put right. Continue moves on. */
export function LearnedCard({ message, note, onContinue }: Props) {
  // one of the three, picked afresh each time the card appears
  const [emoji] = useState(() => EMOJI[Math.floor(Math.random() * EMOJI.length)]);
  useEffect(() => confettiBurst(), []);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Enter' && onContinue();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onContinue]);

  return createPortal(
    <motion.div className="fixed inset-0 z-40 flex items-center justify-center bg-ink/45 p-4" initial={{ opacity: 0 }} animate={{ opacity: 1 }} role="dialog" aria-modal="true" aria-labelledby="learned-title">
      <motion.div
        initial={{ scale: 0.8, y: 24, rotate: -2 }}
        animate={{ scale: 1, y: 0, rotate: 0 }}
        transition={{ type: 'spring', stiffness: 260, damping: 20 }}
        className="w-full max-w-md rounded-[2rem] border-2 border-[#ecd596] bg-[#fff6d8] px-8 py-9 text-center shadow-[0_24px_60px_-18px_rgba(70,41,27,0.55)]"
        style={{ backgroundImage: 'var(--grain)' }}
      >
        <motion.div className="text-7xl leading-none" animate={{ y: [0, -10, 0], rotate: [0, -8, 8, 0] }} transition={{ duration: 1.6, repeat: Infinity, repeatDelay: 0.8 }} aria-hidden>
          {emoji}
        </motion.div>
        <h2 id="learned-title" className="font-display mt-5 text-[2rem] leading-tight text-[#46291b]">
          {message}
        </h2>
        <p className="hand mt-2 text-xl text-[#7a4b22]">Mistakes are just steps forward, Brainy Hamster!</p>
        {note && <p className="chip mt-4 bg-sage-soft font-bold text-sage-deep">{note}</p>}
        <button className="btn btn-primary mt-7 w-full !py-3 !text-[1.05rem]" autoFocus onClick={onContinue}>
          Continue <ArrowRight size={18} />
        </button>
      </motion.div>
    </motion.div>,
    document.body,
  );
}
