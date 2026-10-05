import { CircleCheck, RotateCcw } from 'lucide-react';
import { useEffect, useState } from 'react';
import { api, messageOf } from '../../api/client';
import type { OptionId, RetryResult, RetryStep } from '../../api/types';
import { useStore } from '../../store/useStore';
import { ConfidenceMeter } from '../ConfidenceMeter';
import { MCQOptions } from '../MCQOptions';
import { QuestionCard } from '../QuestionCard';
import { HamstarMascot } from '../mascot/HamstarMascot';
import { MascotSays } from '../mascot/HamstarAnimation';
import { AnalysisCard } from './AnalysisCard';

/**
 * Targeted help, then a retest. The server decides whether the mistake now counts as corrected:
 * only when understanding, judged on the retest answer, is above 70%.
 */
export function RemediationFlow({ mistakeId, onDone }: { mistakeId: string; onDone: () => void }) {
  const celebrate = useStore((s) => s.celebrate);
  const [phase, setPhase] = useState<'explain' | 'retry' | 'result'>('explain');
  const [step, setStep] = useState<RetryStep | null>(null);
  const [result, setResult] = useState<RetryResult | null>(null);
  const [pick, setPick] = useState<OptionId | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const load = async () => {
    setError('');
    try {
      setStep(await api.post<RetryStep>(`/api/mistakes/${mistakeId}/retry`));
      setPick(null);
      setPhase('explain');
    } catch (e) {
      setError(messageOf(e));
    }
  };
  useEffect(() => {
    load();
  }, [mistakeId]); // eslint-disable-line react-hooks/exhaustive-deps

  const submit = async () => {
    if (!step || !pick) return;
    setBusy(true);
    setError('');
    try {
      const r = await api.post<RetryResult>(`/api/mistakes/${mistakeId}/retry/evaluate`, { question_id: step.question.id, selected_option: pick });
      setResult(r);
      celebrate(r.unlocked);
      setPhase('result');
    } catch (e) {
      setError(messageOf(e));
    } finally {
      setBusy(false);
    }
  };

  if (!step) {
    return (
      <div className="flex flex-col items-center gap-3 py-10 text-center">
        <HamstarMascot state={error ? 'wrong' : 'reading'} size={150} />
        <p className={error ? 'text-rose' : 'text-ink-soft'}>{error || 'Getting your help ready…'}</p>
        {error && (
          <button className="btn btn-ghost" onClick={load}>
            Try again
          </button>
        )}
      </div>
    );
  }

  if (phase === 'explain') {
    return (
      <div className="space-y-5">
        <MascotSays state="explaining">{step.retry_number === 1 ? 'Here is the idea that sorts this out. Read it through, then try one more question.' : 'Let us look at it once more, slowly. The last answer shows where it goes wrong.'}</MascotSays>
        <AnalysisCard help={step.help} />
        <div className="flex justify-end">
          <button className="btn btn-primary" onClick={() => setPhase('retry')}>
            <RotateCcw size={16} /> Try a retry question
          </button>
        </div>
      </div>
    );
  }

  if (phase === 'retry') {
    return (
      <div className="space-y-5">
        <MascotSays state="encouraging">Take your time. This one checks the same idea on a fresh problem.</MascotSays>
        <QuestionCard accent="sage" prompt={step.question.prompt} eyebrow={<span className="chip bg-sage-soft text-sage-deep">Retry question {step.retry_number}</span>}>
          <MCQOptions question={step.question} selected={pick} onSelect={setPick} disabled={busy} />
          <div className="mt-5 flex items-center justify-end gap-3">
            {error && <span className="text-sm text-rose">{error}</span>}
            <button className="btn btn-primary" disabled={!pick || busy} onClick={submit}>
              {busy ? 'Checking…' : 'Check my answer'}
            </button>
          </div>
        </QuestionCard>
      </div>
    );
  }

  const r = result!;
  return (
    <div className="space-y-5">
      <MascotSays state={r.corrected ? 'celebrating' : 'thinking'}>
        {r.corrected ? 'That is the idea, applied correctly on a new problem.' : r.can_retry_again ? 'Not quite yet. That is fine, we will look at it again.' : 'Not there yet, and that is fine. I have saved this so you can come back to it.'}
      </MascotSays>
      <QuestionCard accent="sage" prompt={r.question.prompt} eyebrow={<span className="chip bg-sage-soft text-sage-deep">Retry question {step.retry_number}</span>}>
        <MCQOptions question={r.question} selected={r.selected_option} disabled reveal="all" />
        <p className="mt-4 text-sm text-ink-soft">{r.question.solution}</p>
      </QuestionCard>
      <section className="card p-5">
        <ConfidenceMeter label="Understanding confidence" tone="understanding" value={r.understanding / 100} from={0.5} />
        <p className="mt-3 text-sm">
          {r.corrected ? (
            <span className="inline-flex items-center gap-2 font-semibold text-sage-deep">
              <CircleCheck size={18} /> Mistake corrected · +1 towards Mistake Master
            </span>
          ) : (
            <span className="text-ink-soft">Understanding confidence is {Math.round(r.understanding)}%. A mistake counts as corrected only above 70%.</span>
          )}
        </p>
      </section>
      <div className="flex justify-end">
        {r.can_retry_again ? (
          <button className="btn btn-primary" onClick={load}>
            Look at it again
          </button>
        ) : (
          <button className="btn btn-primary" onClick={onDone}>
            Continue
          </button>
        )}
      </div>
    </div>
  );
}
