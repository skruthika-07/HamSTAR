import { Crosshair } from 'lucide-react';
import type { OptionId, Question, Step } from '../../api/types';
import { pct } from '../ConfidenceMeter';
import { MCQOptions } from '../MCQOptions';
import { QuestionCard } from '../QuestionCard';

interface Props {
  question: Question;
  /** Expected information gain, in bits, when the question was chosen. */
  gain: number;
  index: number;
  selected: OptionId | null;
  onSelect: (id: OptionId) => void;
  answered: boolean;
}

/** A follow-up picked because the competing explanations predict different answers to it. */
export function FollowUpQuestion({ question, gain, index, selected, onSelect, answered }: Props) {
  return (
    <QuestionCard
      accent="lavender"
      prompt={question.prompt}
      eyebrow={
        <>
          <span className="chip bg-lavender-soft text-lavender-deep">
            <Crosshair size={13} /> Targeted follow-up {index}
          </span>
          <span className="normal-case tracking-normal text-ink-soft" data-tip="Expected information gain: how much this answer is expected to reduce uncertainty between the explanations">
            Chosen to separate the two explanations · {gain.toFixed(2)} bits expected
          </span>
        </>
      }
    >
      <MCQOptions question={question} selected={selected} onSelect={onSelect} disabled={answered} reveal={answered ? 'own' : 'none'} />
    </QuestionCard>
  );
}

/** Shown after the answer: what each explanation predicted, and what the student actually chose. */
export function FollowUpRationale({ step }: { step: Step }) {
  const rows = [
    step.expected_if_misconception && { label: 'If a misconception were at work', p: step.expected_if_misconception, tone: 'bg-lavender-soft' },
    step.expected_if_slip && { label: 'If it was a careless slip', p: step.expected_if_slip, tone: 'bg-sage-soft' },
  ].filter(Boolean) as { label: string; p: NonNullable<Step['expected_if_slip']>; tone: string }[];

  return (
    <div className="card p-5">
      <div className="eyebrow mb-3">Why this question</div>
      <div className="space-y-2">
        {rows.map((r) => (
          <div key={r.label} className={`flex flex-wrap items-center justify-between gap-2 rounded-xl px-3.5 py-2.5 text-sm ${r.tone}`}>
            <span>{r.label}</span>
            <span className="font-semibold">
              expected <span className="math text-base">{r.p.text}</span> <span className="font-normal text-ink-soft">({pct(r.p.probability)})</span>
            </span>
          </div>
        ))}
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border-2 border-ink px-3.5 py-2.5 text-sm">
          <span className="font-semibold">You answered</span>
          <span className="math text-base font-semibold">{step.selected.text}</span>
        </div>
      </div>
      <p className="mt-3 text-xs text-ink-soft">
        {step.discriminates ? 'The two explanations predict different answers here, so your answer counts as evidence for one and against the other.' : 'This question checks whether the same idea holds up on a fresh problem.'}
      </p>
    </div>
  );
}
