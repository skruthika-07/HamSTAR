import { motion } from 'framer-motion';
import type { Summary } from '../api/types';

/** A conclusion needs MORE than this. The server enforces it; this only draws the line on the bars. */
export const CONFIDENCE_THRESHOLD = 0.7;

export const pct = (x: number) => `${Math.round(x * 100)}%`;

type Tone = 'misconception' | 'slip' | 'unexplained' | 'calculation' | 'understanding';
// the same colours as the four kinds of mistake everywhere else
const TONES: Record<Tone, string> = {
  misconception: 'bg-[#ef4444]',
  slip: 'bg-[#eab308]',
  unexplained: 'bg-[#f97316]',
  calculation: 'bg-[#3b82f6]',
  understanding: 'bg-gold',
};

/** A probability bar with the 70% decision threshold marked on it. */
export function ConfidenceMeter({ label, value, tone, from }: { label: string; value: number; tone: Tone; from?: number }) {
  const passed = value > CONFIDENCE_THRESHOLD;
  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between gap-3 text-sm">
        <span className="font-medium">{label}</span>
        <span className="tabular-nums">
          {from !== undefined && <span className="text-ink-soft">{pct(from)} → </span>}
          <span className={`font-bold ${passed ? 'text-ink' : 'text-ink-soft'}`}>{pct(value)}</span>
        </span>
      </div>
      <div className="relative h-3 rounded-full bg-cream-2">
        <motion.div className={`h-3 rounded-full ${TONES[tone]}`} initial={{ width: `${(from ?? 0) * 100}%` }} animate={{ width: `${value * 100}%` }} transition={{ duration: 0.9, ease: 'easeOut' }} />
        <span className="absolute -top-1 h-5 w-0.5 rounded bg-ink/70" style={{ left: `${CONFIDENCE_THRESHOLD * 100}%` }} title="70% threshold" />
      </div>
    </div>
  );
}

/** The four competing explanations side by side, optionally showing how evidence moved them. */
export function EvidenceBars({ summary, before }: { summary: Summary; before?: Summary }) {
  return (
    <div className="space-y-3">
      <ConfidenceMeter label="Misconception" tone="misconception" value={summary.misconception} from={before?.misconception} />
      <ConfidenceMeter label="Gap in understanding" tone="unexplained" value={summary.unexplained} from={before?.unexplained} />
      <ConfidenceMeter label="Careless slip" tone="slip" value={summary.slip} from={before?.slip} />
      <ConfidenceMeter label="Calculation error" tone="calculation" value={summary.calculation ?? 0} from={before?.calculation} />
      <p className="text-xs text-ink-soft">The line marks 70%. HamSTAR only states a diagnosis once one explanation passes it.</p>
    </div>
  );
}
