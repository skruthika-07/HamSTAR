import { motion } from 'framer-motion';
import { Check, X } from 'lucide-react';
import type { OptionId, Question } from '../api/types';

interface Props {
  question: Question;
  selected: OptionId | null;
  onSelect?: (id: OptionId) => void;
  /** 'none' hides correctness, 'own' marks only the chosen option, 'all' also shows the correct one. */
  reveal?: 'none' | 'own' | 'all';
  disabled?: boolean;
}

export function MCQOptions({ question, selected, onSelect, reveal = 'none', disabled }: Props) {
  return (
    <div className="grid gap-2.5 sm:grid-cols-2" role="radiogroup" aria-label="Answer options">
      {question.options.map((o) => {
        const isSel = selected === o.id;
        const showRight = (reveal === 'all' && o.correct) || (reveal === 'own' && isSel && o.correct);
        const showWrong = reveal !== 'none' && isSel && !o.correct;
        const style = showRight
          ? 'border-sage-deep bg-sage-soft'
          : showWrong
            ? 'border-rose bg-rose-soft'
            : isSel
              ? 'border-lavender-deep bg-lavender-soft shadow-[0_0_0_4px_rgba(138,102,201,0.16)]'
              : 'border-line bg-paper text-ink hover:border-oak hover:bg-cream';
        return (
          <button
            key={o.id}
            type="button"
            role="radio"
            aria-checked={isSel}
            disabled={disabled}
            onClick={() => onSelect?.(o.id)}
            className={`mcq-option flex items-center gap-3 rounded-xl border-2 px-3.5 py-3 text-left text-ink transition-all duration-200 ease-out ${style} ${disabled ? 'cursor-default' : 'cursor-pointer'}`}
          >
            <motion.span animate={{ scale: isSel ? [1, 1.18, 1] : 1 }} transition={{ duration: 0.3 }} className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-sm font-bold transition-colors duration-200 ${isSel ? 'bg-ink text-cream' : 'bg-cream-2 text-ink-soft'}`}>
              {o.id}
            </motion.span>
            <span className="math flex-1 text-lg">{o.text}</span>
            {showRight && <Check size={20} className="text-sage-deep" />}
            {showWrong && <X size={20} className="text-rose" />}
          </button>
        );
      })}
    </div>
  );
}
