import { motion } from 'framer-motion';
import { ArrowRight, Calculator, Check, CircleX, Puzzle, RotateCcw, Shuffle } from 'lucide-react';
import { useEffect, useState } from 'react';
import { api, messageOf } from '../../api/client';
import type { ConceptFollowUp, ConceptFollowUpResult, Diagnostic, Explanation, FollowUp, MistakeKind, OptionId, Question, RetryResult, RetryStep, WrittenFeedback } from '../../api/types';
import { useStore } from '../../store/useStore';
import { MCQOptions } from '../MCQOptions';
import { HamstarAnimation, MascotSays } from '../mascot/HamstarAnimation';
import { HamstarMascot } from '../mascot/HamstarMascot';
import { StructuredAnswer } from '../StructuredAnswer';
import { StructuredFeedback } from '../StructuredFeedback';
import { LearnedCard } from '../LearnedCard';
import { RecurringWarning } from '../RecurringMistakes';
import { DiagnosisCard } from './DiagnosisCard';
import { KINDS } from '../../data/mistakeKinds';

// how each kind of mistake is shown above the explanation
const MISTAKE: Record<MistakeKind, { icon: typeof Check; tone: string }> = {
  CARELESS_SLIP: { icon: Shuffle, tone: KINDS.careless_slip.chip },
  MISCONCEPTION: { icon: CircleX, tone: KINDS.misconception.chip },
  GAP_IN_UNDERSTANDING: { icon: Puzzle, tone: KINDS.gap_in_understanding.chip },
  CALCULATION_ERROR: { icon: Calculator, tone: KINDS.calculation_error.chip },
};

// said after a follow-up is answered correctly; a different one each time
const CHEERS = [
  'You learned from your mistake!',
  "That's the HamSTAR spirit: mistakes are just steps forward!",
  'Look at you go! You got it this time!',
  'Cheeks full of knowledge! That one is yours now.',
  'Wheel spinning, bulb glowing: you cracked it!',
  'From oops to got-it in one go. Proud hamster here!',
];
let cheerIndex = Math.floor(Math.random() * CHEERS.length);
const nextCheer = () => CHEERS[cheerIndex++ % CHEERS.length];

type Stage = 'intro' | 'explain' | 'ask' | 'done';

interface Props {
  attemptId: string;
  /** The investigation the server opened for a wrong multiple-choice answer. Absent for written answers. */
  diagnostic: Diagnostic | null;
  /** Shown above the correct answer for written answers, e.g. "3 of 8 marks". */
  marksNote?: string;
  /** For written answers: what was matched, covered and missed. */
  feedback?: WrittenFeedback;
  /** Set when this concept has now gone wrong twice or more. */
  recurring?: { concept: string; count: number; message: string } | null;
  /** True inside a mini-drill, where offering another drill would be going in circles. */
  inDrill?: boolean;
  onFinish: () => void;
}

/**
 * What follows a wrong answer:
 *
 *   the kind of mistake  →  the correct answer in four parts (key terms, core concepts, full explanation, remember)
 *     →  "I Understood"  →  a follow-up question on the same idea
 *                            right: a cheer · wrong: explained again more simply, then one more follow-up
 *     →  "Explain Again" →  the same idea in simpler words, with an everyday example
 *
 * Multiple-choice answers get their follow-ups from the diagnosis; written answers get one written by the AI.
 *
 * The student is not told why their answer was wrong up front. Behind the scenes the follow-up is still
 * the question that best tells a misconception from a slip, and what was found is shown at the end.
 */
export function WrongAnswerFlow({ attemptId, diagnostic, marksNote, feedback, recurring, inDrill, onFinish }: Props) {
  const celebrate = useStore((s) => s.celebrate);
  const [view, setView] = useState<Diagnostic | null>(diagnostic);
  const [stage, setStage] = useState<Stage>('intro');
  const [explanation, setExplanation] = useState<Explanation | null>(null);
  // which of the session's questions is being explained (the original one when null)
  const [target, setTarget] = useState<string | null>(null);
  const [ask, setAsk] = useState<{ kind: 'followup' | 'retry' | 'concept'; question: Question; note: string } | null>(null);
  const [pick, setPick] = useState<OptionId | null>(null);
  const [canRetry, setCanRetry] = useState(true);
  const [cheer, setCheer] = useState('');
  // written answers: whether a follow-up was answered correctly, and whether one more may be asked
  const [recovered, setRecovered] = useState(false);
  const [another, setAnother] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const sid = view?.session_id;

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError('');
    try {
      await fn();
    } catch (e) {
      setError(messageOf(e));
    } finally {
      setBusy(false);
    }
  };

  /** Fetch the correct answer and its explanation. Each higher level is simpler, with an everyday example. */
  const explain = (level: number, questionId: string | null) =>
    run(async () => {
      const e = sid ? await api.post<Explanation>(`/api/diagnostics/${sid}/explain`, { level, question_id: questionId }) : await api.post<Explanation>(`/api/attempts/${attemptId}/explain`, { level, question_id: questionId });
      setExplanation(e);
      setTarget(questionId);
      setStage('explain');
    });

  // the hamster reacts first (the bulb cracks), then starts explaining
  useEffect(() => {
    const t = setTimeout(() => explain(0, null), 1900);
    return () => clearTimeout(t);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const finish = (latest: Diagnostic | null) =>
    run(async () => {
      if (latest) setView(await api.get<Diagnostic>(`/api/diagnostics/${latest.session_id}`));
      setStage('done');
    });

  /** "I Understood": test it with a question on the same idea. */
  const understood = (current: Diagnostic | null = view, praise = ''): Promise<void> =>
    run(async () => {
      if (!current) {
        // written answers: a new question on the same concept (after a miss, one more that is a little easier)
        if (target && !another) return void setStage('done');
        try {
          const f = await api.post<ConceptFollowUp>(`/api/attempts/${attemptId}/followup`);
          setAsk({ kind: 'concept', note: f.number > 1 ? 'One more on the same idea, a little easier this time.' : "Let's check it with a question on the same idea.", question: f.question });
          setPick(null);
          setStage('ask');
        } catch {
          // no follow-up could be written just now: carry on rather than leave the student stuck
          if (target) setStage('done');
          else onFinish();
        }
        return;
      }
      if (current.corrected) return void (await finish(current));
      if (!current.diagnosis) {
        const f = await api.post<FollowUp>(`/api/diagnostics/${current.session_id}/followup`);
        if (f.question) {
          setAsk({ kind: 'followup', note: praise ? `${praise} One more to be sure.` : "Let's check it with a question on the same idea.", question: { id: f.question_id, topic: current.question.topic, type: 'MCQ', marks: 1, prompt: f.question, options: f.options } });
          setPick(null);
          setStage('ask');
          return;
        }
        if (f.diagnostic) {
          setView(f.diagnostic);
          current = f.diagnostic;
        }
      }
      if (current.corrected || !canRetry) return void (await finish(current));
      // the cause is known by now: one more question on the same idea decides whether it has been put right
      const step = await api.post<RetryStep>(`/api/mistakes/${current.session_id}/retry`);
      setAsk({ kind: 'retry', note: praise ? `${praise} One more to make sure it has stuck.` : 'One more on the same idea, to make sure it has stuck.', question: step.question });
      setPick(null);
      setStage('ask');
    });

  const submit = () =>
    run(async () => {
      if (!ask || !pick) return;
      if (ask.kind === 'concept') {
        const r = await api.post<ConceptFollowUpResult>(`/api/attempts/${attemptId}/followup/evaluate`, { question_id: ask.question.id, selected_option: pick });
        setAnother(r.can_try_another);
        if (!r.is_correct) return void (await explain(1, r.question.id)); // wrong again: simpler words this time
        setCheer(nextCheer());
        setRecovered(true);
        return void setStage('done');
      }
      if (!sid) return;
      if (ask.kind === 'followup') {
        const next = await api.post<Diagnostic>(`/api/diagnostics/${sid}/evaluate-followup`, { answer: pick });
        setView(next);
        celebrate(next.unlocked);
        const last = next.steps[next.steps.length - 1];
        if (!last.is_correct) return void (await explain(1, last.question.id)); // wrong again: simpler words this time
        const said = nextCheer();
        setCheer(said);
        if (next.corrected) return void (await finish(next));
        return void (await understood(next, said));
      }
      const r = await api.post<RetryResult>(`/api/mistakes/${sid}/retry/evaluate`, { question_id: ask.question.id, selected_option: pick });
      celebrate(r.unlocked);
      setCanRetry(r.can_retry_again);
      if (r.corrected) {
        setCheer(nextCheer());
        return void (await finish(view));
      }
      await explain(1, r.question.id);
    });

  const problem = error && (
    <p className="text-right text-sm text-rose">
      {error}{' '}
      <button className="cursor-pointer underline" onClick={() => (stage === 'intro' ? explain(0, null) : setError(''))}>
        {stage === 'intro' ? 'Try again' : 'Dismiss'}
      </button>
    </p>
  );

  if (stage === 'intro') {
    return (
      <>
        <motion.section initial={{ x: 0 }} animate={{ x: [0, -5, 5, -3, 3, 0] }} transition={{ duration: 0.45, delay: 0.5 }} className="card flex min-h-[26rem] flex-col items-center justify-center gap-3 px-6 py-8 text-center">
          <div className="px-10 pt-6">
            <HamstarAnimation size={240} steps={[{ state: 'wrong', ms: 1500 }, { state: 'explaining', ms: 0 }]} />
          </div>
          <p className="font-display text-2xl text-[#46291b]" aria-live="polite">
            Not quite. Let me show you how this one works.
          </p>
        </motion.section>
        {problem}
      </>
    );
  }

  if (stage === 'explain' && explanation) {
    const mistake = explanation.mistake_type;
    const look = mistake ? (MISTAKE[mistake.kind] ?? MISTAKE.GAP_IN_UNDERSTANDING) : null;
    const MistakeIcon = look?.icon ?? null;
    return (
      <div className="space-y-5">
        <MascotSays state="explaining">{explanation.simpler && !target ? 'Here it is another way, with an example.' : target ? 'Not this time, and that is fine. Here it is in simpler words.' : 'Here is the answer, and how to get there.'}</MascotSays>
        {recurring && !target && <RecurringWarning recurring={recurring} showDrill={!inDrill} />}
        <motion.section key={`${target}-${explanation.level}`} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }} className="card p-5 sm:p-7">
          {mistake && MistakeIcon && (
            <div className={`mb-4 flex items-center gap-3 rounded-2xl border-[1.5px] px-4 py-3 ${look?.tone}`} role="status">
              <MistakeIcon size={26} className="shrink-0" />
              <div>
                <div className="font-extrabold">{mistake.message}</div>
                <div className="text-sm text-ink">{mistake.about} Here is how it works.</div>
              </div>
            </div>
          )}
          <p className="math text-lg font-bold">{explanation.question.prompt}</p>
          {marksNote && !target && <p className="mt-1 text-sm font-bold">{marksNote}</p>}
          {feedback && !target && (
            <div className="mt-3">
              <StructuredFeedback feedback={feedback} showExplanation={false} />
            </div>
          )}
          <div className="mt-4 rounded-2xl bg-sage-soft px-5 py-4">
            <div className="eyebrow text-sage-deep">Correct answer</div>
            <div className={`math font-bold text-sage-deep ${explanation.correct_answer.text.length > 60 ? 'text-base leading-relaxed' : 'text-2xl'}`}>{explanation.correct_answer.text}</div>
          </div>
          <div className="mt-5">
            <StructuredAnswer keyTerms={explanation.key_terms ?? []} coreConcepts={explanation.core_concepts ?? []} explanation={explanation.explanation} remember={explanation.remember ?? ''} simpler={explanation.simpler} />
          </div>
          <div className="mt-6 flex flex-wrap justify-end gap-3">
            <button className="btn btn-ghost" disabled={busy} onClick={() => explain(explanation.level + 1, target)}>
              <RotateCcw size={17} /> Explain Again
            </button>
            <button className="btn btn-primary" disabled={busy} onClick={() => understood()}>
              <Check size={18} /> I Understood
            </button>
          </div>
          {problem}
        </motion.section>
      </div>
    );
  }

  if (stage === 'ask' && ask) {
    return (
      <div className="space-y-5">
        <MascotSays state="question">{ask.note}</MascotSays>
        <section className="card p-5 sm:p-7">
          <div className="eyebrow">{ask.kind === 'retry' ? 'Check question' : 'Follow-up question'}</div>
          <p className="math mb-5 mt-1 text-2xl leading-snug font-bold">{ask.question.prompt}</p>
          <MCQOptions question={ask.question} selected={pick} onSelect={setPick} disabled={busy} />
          <div className="mt-6 flex items-center justify-end gap-3">
            <button className="btn btn-primary" disabled={!pick || busy} onClick={submit}>
              {busy ? 'Checking…' : 'Check my answer'} <ArrowRight size={18} />
            </button>
          </div>
          {problem}
        </section>
      </div>
    );
  }

  if (stage === 'done') {
    const corrected = !!view?.corrected || recovered;
    // put right: a flashcard in the middle of the screen, and Continue goes on to the next question
    if (corrected) return <LearnedCard message={cheer || 'You learned from your mistake!'} note={view?.corrected ? 'Mistake corrected · +1 towards Mistake Master' : undefined} onContinue={onFinish} />;
    return (
      <div className="space-y-5">
        <MascotSays state={corrected ? 'celebrating' : 'encouraging'}>
          {corrected ? cheer || 'That is it! You showed you understand it now.' : view ? 'Good effort. I have saved this one in Past Mistakes so we can come back to it.' : 'Good effort. This idea takes a little practice, and we will meet it again.'}
        </MascotSays>
        {recurring && <RecurringWarning recurring={recurring} showDrill={!inDrill} />}
        {view?.diagnosis && (
          <>
            <div className="eyebrow">What I noticed along the way</div>
            <DiagnosisCard diagnosis={view.diagnosis} feedback={view.feedback} followUps={view.steps.length} />
          </>
        )}
        <div className="flex flex-wrap items-center justify-between gap-3">
          {view?.corrected ? <span className="chip bg-sage-soft font-bold text-sage-deep">Mistake corrected · +1 towards Mistake Master</span> : recovered ? <span className="chip bg-sage-soft font-bold text-sage-deep">You learned from that mistake</span> : <span />}
          <button className="btn btn-primary" onClick={onFinish}>
            Continue <ArrowRight size={18} />
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center gap-3 py-10 text-center">
      <HamstarMascot state="thinking" size={150} />
      <p className="text-ink-soft">One moment…</p>
      {problem}
    </div>
  );
}
