import { motion } from 'framer-motion';
import { Calculator, CircleHelp, Pencil, Puzzle, Search } from 'lucide-react';
import type { Diagnosis, VerdictKind } from '../../api/types';
import { kindOf } from '../../data/mistakeKinds';

const VIEW: Record<string, { title: string; icon: typeof Search }> = {
  misconception: { title: 'Likely misconception', icon: Search },
  careless_slip: { title: 'Likely careless slip', icon: Pencil },
  gap_in_understanding: { title: 'Likely gap in understanding', icon: Puzzle },
  calculation_error: { title: 'Likely calculation error', icon: Calculator },
  inconclusive: { title: 'Not enough evidence yet', icon: CircleHelp },
};

export function verdictLabel(kind: VerdictKind): string {
  return kindOf(kind).label;
}

/** The diagnosis, stated only after the follow-up evidence is in. The wording of the explanation comes from the server. */
export function DiagnosisCard({ diagnosis, feedback, followUps }: { diagnosis: Diagnosis; feedback: string; followUps: number }) {
  const v = VIEW[diagnosis.verdict] ?? VIEW.inconclusive;
  const k = kindOf(diagnosis.verdict);
  const Icon = v.icon;
  const strong = diagnosis.status !== 'UNCERTAIN';
  const title = v.title;

  return (
    <motion.section initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }} className="card border-2 p-5 sm:p-6" style={{ borderColor: k.color }}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <span className={`flex h-12 w-12 items-center justify-center rounded-2xl border ${k.chip}`}>
            <Icon size={24} />
          </span>
          <div>
            <div className="eyebrow">Diagnosis</div>
            <h3 className="text-xl font-semibold sm:text-2xl">{title}</h3>
            {diagnosis.misconception && <div className="font-bold" style={{ color: k.color }}>{diagnosis.misconception.name}</div>}
            {diagnosis.verdict !== 'inconclusive' && <p className="mt-0.5 max-w-md text-sm text-ink-soft">{diagnosis.meaning ?? k.meaning}</p>}
          </div>
        </div>
        <div className="text-right" data-tip="How strongly the evidence supports this explanation. A diagnosis needs more than 70%.">
          <div className="eyebrow">Diagnostic confidence</div>
          <div className="font-display text-4xl font-semibold tabular-nums">{Math.round(diagnosis.confidence)}%</div>
          <div className="text-xs text-ink-soft">{diagnosis.band}</div>
        </div>
      </div>

      <p className="mt-4 text-[0.95rem] leading-relaxed">{feedback}</p>

      <p className="mt-3 rounded-xl bg-cream px-3.5 py-2.5 text-sm text-ink-soft">
        {strong
          ? `Confidence is above 70% after ${followUps} follow-up ${followUps === 1 ? 'question' : 'questions'}, which is strong enough to act on.`
          : `Confidence is at or below 70% after ${followUps} follow-up ${followUps === 1 ? 'question' : 'questions'}. More evidence is needed before drawing a conclusion.`}
      </p>
    </motion.section>
  );
}
