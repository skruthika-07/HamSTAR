import { CircleCheck, RotateCcw } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import type { MistakeStatus } from '../api/types';
import { useFolderName } from '../data/topics';
import type { MistakeRecord } from '../store/useStore';
import { EvidenceBars } from './ConfidenceMeter';
import { kindOf } from '../data/mistakeKinds';


export const STATUS_LABEL: Record<MistakeStatus, string> = {
  NEEDS_REVIEW: 'Needs Review',
  MISCONCEPTION_IDENTIFIED: 'Misconception Identified',
  SLIP_IDENTIFIED: 'Slip Identified',
  GAP_IDENTIFIED: 'Gap Identified',
  CALCULATION_IDENTIFIED: 'Calculation Error Identified',
  CORRECTED: 'Corrected',
};

/** One diagnosed mistake as a learning record. Everything on it was decided by the server. */
export function PastMistakeCard({ mistake }: { mistake: MistakeRecord }) {
  const [open, setOpen] = useState(false);
  const topic = useFolderName()(mistake.topic);

  return (
    <article className="card p-5" style={{ borderLeft: `6px solid ${kindOf(mistake.verdict).color}` }}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="eyebrow">
            {topic} · {new Date(mistake.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
          </div>
          <h3 className="math mt-0.5 text-xl font-semibold">{mistake.question.prompt}</h3>
        </div>
        <span className={`chip font-bold ${mistake.corrected ? 'bg-sage-soft text-sage-deep' : `border ${kindOf(mistake.verdict).chip}`}`}>
          {mistake.corrected && <CircleCheck size={13} />}
          {STATUS_LABEL[mistake.status]}
        </span>
      </div>

      <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-4">
        <div className="rounded-xl bg-rose-soft px-3 py-2">
          <dt className="eyebrow text-rose">Your answer</dt>
          <dd className="math text-lg font-semibold">{mistake.selected.text}</dd>
        </div>
        <div className="rounded-xl bg-sage-soft px-3 py-2">
          <dt className="eyebrow text-sage-deep">Correct answer</dt>
          <dd className="math text-lg font-semibold">{mistake.correct.text}</dd>
        </div>
        <div className="rounded-xl bg-cream px-3 py-2">
          <dt className="eyebrow">Diagnosis</dt>
          <dd>
            <span className={`chip mt-0.5 border font-bold ${kindOf(mistake.verdict).chip}`}>{kindOf(mistake.verdict).label}</span>
          </dd>
        </div>
        <div className="rounded-xl bg-cream px-3 py-2">
          <dt className="eyebrow">Confidence</dt>
          <dd className="font-display text-lg font-semibold tabular-nums">{Math.round(mistake.confidence)}%</dd>
        </div>
      </dl>

      {mistake.verdict !== 'inconclusive' && (
        <p className="mt-3 text-sm italic text-ink-soft">{mistake.meaning ?? kindOf(mistake.verdict).meaning}</p>
      )}
      <p className="mt-2 text-sm leading-relaxed">
        <span className="font-semibold">Explanation: </span>
        {mistake.explanation}
      </p>
      {mistake.what_was_learned && (
        <p className="mt-1 text-sm leading-relaxed">
          <span className="font-semibold">What you learned: </span>
          {mistake.what_was_learned}
        </p>
      )}

      {open && (
        <div className="mt-4 space-y-4 border-t border-line pt-4">
          {mistake.reasoning && (
            <p className="text-sm">
              <span className="font-semibold">Your reasoning: </span>
              <em>"{mistake.reasoning}"</em>
            </p>
          )}
          {mistake.steps.map((s, i) => (
            <div key={i} className="rounded-xl bg-cream px-3.5 py-3 text-sm">
              <div className="eyebrow mb-1">Follow-up question {i + 1}</div>
              <div className="math text-base font-semibold">{s.question.prompt}</div>
              <div className="mt-1">
                You answered <span className="math font-semibold">{s.selected.text}</span> <span className={s.is_correct ? 'text-sage-deep' : 'text-rose'}>({s.is_correct ? 'correct' : 'incorrect'})</span>
              </div>
            </div>
          ))}
          <div>
            <div className="eyebrow mb-2">How the evidence moved</div>
            <EvidenceBars summary={mistake.final} before={mistake.initial} />
          </div>
          {mistake.understanding !== null && <p className="text-sm text-ink-soft">Understanding confidence after the correction step: {Math.round(mistake.understanding)}%.</p>}
        </div>
      )}

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <button className="cursor-pointer text-sm font-semibold text-lavender-deep underline-offset-4 hover:underline" onClick={() => setOpen(!open)} aria-expanded={open}>
          {open ? 'Hide the evidence' : 'Show follow-up and evidence'}
        </button>
        <Link to={`/mistakes/${mistake.id}/retry`} className={`btn ${mistake.corrected ? 'btn-ghost' : 'btn-primary'}`}>
          <RotateCcw size={16} /> {mistake.corrected ? 'Practise again' : 'Retry'}
        </Link>
      </div>
    </article>
  );
}
