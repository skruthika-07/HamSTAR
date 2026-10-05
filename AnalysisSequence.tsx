import { motion } from 'framer-motion';
import { Check, type LucideIcon } from 'lucide-react';
import { useEffect, useState } from 'react';
import { HamstarMascot, type MascotState } from './HamstarMascot';

export interface AnalysisStep {
  label: string;
  icon: LucideIcon;
  /** What the hamster does while this step runs. */
  state: MascotState;
}

interface Props {
  steps: AnalysisStep[];
  /** The last line, shown once every step is done. */
  done: string;
  stepMs?: number;
  size?: number;
  onDone: () => void;
}

/**
 * The loading screen: no spinner, the hamster does the work in the middle of the page
 * while the stages of the analysis tick off beneath it.
 */
export function AnalysisSequence({ steps, done, stepMs = 650, size = 230, onDone }: Props) {
  const [i, setI] = useState(0);
  const finished = i >= steps.length;

  useEffect(() => {
    const t = setTimeout(() => (finished ? onDone() : setI(i + 1)), finished ? 550 : stepMs);
    return () => clearTimeout(t);
  }, [i]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <section className="card flex min-h-[34rem] flex-col items-center justify-center gap-4 px-6 py-8" aria-live="polite">
      <HamstarMascot state={finished ? 'confident' : steps[i].state} size={size} />
      <ol className="w-full max-w-xs space-y-1.5">
        {steps.slice(0, i + 1).map((s, n) => {
          const past = n < i;
          return (
            <motion.li key={s.label} initial={{ opacity: 0, y: 6 }} animate={{ opacity: past ? 0.55 : 1, y: 0 }} transition={{ duration: 0.25 }} className={`flex items-center gap-2.5 ${past ? 'text-sm' : 'font-bold'}`}>
              <span className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full ${past ? 'bg-sage-soft text-sage-deep' : 'bg-gold-soft text-gold-deep'}`}>{past ? <Check size={13} strokeWidth={3} /> : <s.icon size={13} strokeWidth={2.4} />}</span>
              {s.label}
              {!past && <span className="dots" aria-hidden />}
            </motion.li>
          );
        })}
        {finished && (
          <motion.li initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="flex items-center gap-2.5 font-extrabold text-sage-deep">
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-sage-deep text-white">
              <Check size={13} strokeWidth={3} />
            </span>
            {done}
          </motion.li>
        )}
      </ol>
      <div className="bar w-full max-w-xs">
        <span className="bg-gold" style={{ width: `${(Math.min(i, steps.length) / steps.length) * 100}%` }} />
      </div>
    </section>
  );
}
