import { motion } from 'framer-motion';
import { ArrowRight, Compass, Lightbulb, RotateCcw, ScanSearch, Search, SkipForward, Target, Upload as UploadIcon } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { ApiError, api, clientKey, messageOf } from '../api/client';
import type { EvalResult, NextQuestion, OptionId, PracticeSet, SetSummary } from '../api/types';
import { RemediationFlow } from '../components/diagnosis/RemediationFlow';
import { VoiceAnswer } from '../components/diagnosis/VoiceAnswer';
import { WrongAnswerFlow } from '../components/diagnosis/WrongAnswerFlow';
import { AppShell } from '../components/layout/AppShell';
import { MCQOptions } from '../components/MCQOptions';
import { AnalysisSequence, type AnalysisStep } from '../components/mascot/AnalysisSequence';
import { HamstarAnimation } from '../components/mascot/HamstarAnimation';
import { HamstarMascot } from '../components/mascot/HamstarMascot';
import { PhotoAttach, YourAnswer, useObjectUrl } from '../components/PhotoAttach';
import { STREAK_MILESTONES, StreakDance } from '../components/StreakDance';
import { confettiBurst } from '../lib/celebrate';
import { QuestionTypeSelector, typeInfo } from '../components/QuestionTypeSelector';
import { RewardAnimation } from '../components/RewardAnimation';
import { StructuredFeedback } from '../components/StructuredFeedback';
import { TiaraFlight, holdTiara, releaseTiara } from '../components/TiaraCounter';
import { useFolderName } from '../data/topics';
import { useStore } from '../store/useStore';

// One request per folder and type at a time, however often the page asks (React's dev mode asks twice).
const writingNow = new Map<string, Promise<unknown>>();
function writeOnce(key: string, start: () => Promise<unknown>): Promise<unknown> {
  let p = writingNow.get(key);
  if (!p) {
    p = start().finally(() => writingNow.delete(key));
    writingNow.set(key, p);
  }
  return p;
}

const CHECKING: AnalysisStep[] = [
  { label: 'Analyzing your answer', icon: ScanSearch, state: 'analyzing' },
  { label: 'Examining what you wrote', icon: Search, state: 'investigating' },
  { label: 'Comparing with the answer key', icon: Lightbulb, state: 'thinking' },
  { label: 'Working out the result', icon: Target, state: 'listening' },
];

/**
 * A learning session. Normally it walks through one document's questions, remembering the position on the server.
 * With `practice` it runs a fixed set instead (a mini-drill on one concept, or one weak document): the answers
 * count, but the document's own position is left where it was.
 */
export function Session({ practice = false }: { practice?: boolean } = {}) {
  // a starter-bank folder id, or the questions written from one upload ("material:<id>")
  const { topic: folder = '' } = useParams();
  const refresh = useStore((s) => s.refresh);
  const celebrate = useStore((s) => s.celebrate);
  const streak = useStore((s) => s.stats.streak);
  const materials = useStore((s) => s.materials);
  const tree = useStore((s) => s.folders.folders);
  const type = useStore((s) => s.questionType);
  const marks = useStore((s) => s.questionMarks[s.questionType]);
  const info = typeInfo(type);

  const [params] = useSearchParams();
  const concept = params.get('concept');
  const target = concept ? `concept=${encodeURIComponent(concept)}` : `document=${encodeURIComponent(params.get('document') ?? '')}`;
  const pool = useRef<PracticeSet | null>(null);
  const at = useRef(0);
  const tally = useRef({ correct: 0, wrong: 0, skipped: 0 });
  const [poolTitle, setPoolTitle] = useState('');

  const [current, setCurrent] = useState<NextQuestion | null>(null);
  // set once every question in this folder (of this type) has been done
  const [summary, setSummary] = useState<SetSummary | null>(null);
  const [pick, setPick] = useState<OptionId | null>(null);
  const [answer, setAnswer] = useState('');
  // a photo of the working, sent with the answer and shown beside it afterwards
  const [photo, setPhoto] = useState<File | null>(null);
  const photoUrl = useObjectUrl(photo);
  // the happy dance for 3, 5 and 10 correct in a row
  const [dance, setDance] = useState(0);
  const [phase, setPhase] = useState<'ask' | 'checking' | 'right' | 'wrong'>('ask');
  const [result, setResult] = useState<EvalResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [writing, setWriting] = useState(false);
  const [error, setError] = useState('');
  // the wheel spins first, then the bulb lights and "Correct!" appears
  const [lit, setLit] = useState(false);

  const isMaterial = folder.startsWith('material:');
  const nameOf = useFolderName();
  // an uploaded folder is named after its subject, whatever that is
  // the document being worked on: its questions are the only ones asked here
  const doc = tree.flatMap((f) => f.subfolders.flatMap((s) => s.documents)).find((d) => d.id === folder);
  const folderName = practice ? poolTitle || (concept ?? 'Practice') : doc ? doc.subject : isMaterial ? (materials.find((m) => `material:${m.id}` === folder)?.subject ?? 'Your material') : nameOf(folder);
  const confidence = doc?.confidence;
  const setActiveDocument = useStore((s) => s.setActiveDocument);
  const query = `${isMaterial ? `material_id=${folder.slice(9)}` : `topic=${encodeURIComponent(folder)}`}&question_type=${type}`;

  const load = async () => {
    setError('');
    setPick(null);
    setAnswer('');
    setPhoto(null);
    setLit(false);
    setResult(null);
    setPhase('ask');
    if (practice) {
      try {
        if (!pool.current) {
          pool.current = await api.get<PracticeSet>(`/api/practice?${target}`);
          setPoolTitle(pool.current.title);
        }
        const p = pool.current;
        const t = tally.current;
        const done = at.current >= p.questions.length;
        const attempted = t.correct + t.wrong;
        setSummary(done ? { total: p.questions.length, attempted, correct: t.correct, wrong: t.wrong, skipped: t.skipped, score: attempted ? Math.round((t.correct / attempted) * 100) : 0 } : null);
        setCurrent(done ? null : { question: p.questions[at.current], number: at.current + 1, total: p.questions.length, folder: '' });
      } catch (e) {
        setCurrent(null);
        setSummary(null);
        setError(messageOf(e));
      }
      return;
    }
    // the end of the set is an end: a summary, not the first question again
    const show = (r: NextQuestion) => {
      setSummary(r.completed ? (r.summary ?? null) : null);
      setCurrent(r.completed ? null : r);
    };
    try {
      show(await api.get<NextQuestion>(`/api/questions/next?${query}`));
    } catch (e) {
      setSummary(null);
      setCurrent(null);
      if (!(e instanceof ApiError) || e.code !== 'NO_QUESTIONS_OF_TYPE') return setError(messageOf(e));
      // none of this type yet in this folder: have them written, then carry on
      setWriting(true);
      try {
        await writeOnce(query, () => api.post('/api/questions/generate', { ...(isMaterial ? { study_material_id: folder.slice(9) } : { folder }), question_type: type, marks, number_of_questions: info.batch, difficulty: 'medium' }));
        show(await api.get<NextQuestion>(`/api/questions/next?${query}`));
        refresh().catch(() => {});
      } catch (e2) {
        setError(`I couldn't write ${info.label} questions for this folder just now. ${messageOf(e2)}`);
      } finally {
        setWriting(false);
      }
    }
  };
  // a new folder, or a different question type or mark value, starts from that list's next question
  useEffect(() => {
    // opening a document makes it the active one; another document has its own questions and its own place
    if (!practice && folder) setActiveDocument(folder);
    // a practice set starts from its first question each time it is opened
    pool.current = null;
    at.current = 0;
    tally.current = { correct: 0, wrong: 0, skipped: 0 };
    load();
    // leaving mid-reveal must not leave the Tiara counter held back
    return releaseTiara;
  }, [folder, type, marks, practice, target]); // eslint-disable-line react-hooks/exhaustive-deps

  const next = async () => {
    await refresh().catch(() => {});
    await load();
  };

  const isMcq = current?.question.type === 'MCQ';
  const long = current?.question.type === 'SHORT_ANSWER' || current?.question.type === 'LONG_ANSWER';
  const ready = isMcq ? !!pick : answer.trim().length > 0;

  const check = async () => {
    if (!current || !ready) return;
    setBusy(true);
    setError('');
    // the counter waits for the crown to fly over before it ticks up
    holdTiara();
    try {
      let image_id: string | undefined;
      if (photo) {
        const form = new FormData();
        form.append('file', photo);
        image_id = (await api.post<{ id: string }>('/api/answer-images', form)).id;
      }
      const r = await api.post<EvalResult>('/api/attempts/evaluate', { question_id: current.question.id, ...(isMcq ? { selected_option: pick } : { answer: answer.trim() }), client_key: clientKey(), practice, image_id });
      setResult(r);
      // the streak lives here too: up by one on a right answer, back to 0 on a wrong one
      useStore.setState((s) => ({ stats: { ...s.stats, streak: r.current_streak ?? (r.is_correct ? s.stats.streak + 1 : 0) } }));
      if (practice) {
        at.current += 1;
        tally.current[r.is_correct ? 'correct' : 'wrong'] += 1;
      }
      if (r.is_correct) await refresh().catch(() => {});
      else releaseTiara();
      setPhase('checking');
    } catch (e) {
      releaseTiara();
      setError(messageOf(e));
    } finally {
      setBusy(false);
    }
  };

  const skip = async () => {
    if (!current) return;
    setBusy(true);
    try {
      await api.post('/api/attempts', { question_id: current.question.id, skipped: true, client_key: clientKey(), practice });
      if (practice) {
        at.current += 1;
        tally.current.skipped += 1;
      }
      await next();
    } catch (e) {
      setError(messageOf(e));
    } finally {
      setBusy(false);
    }
  };

  const again = async () => {
    setBusy(true);
    try {
      if (practice) {
        pool.current = null;
        at.current = 0;
        tally.current = { correct: 0, wrong: 0, skipped: 0 };
      } else
        await api.post('/api/questions/restart', { ...(isMaterial ? { material_id: folder.slice(9) } : { topic: folder }), question_type: type });
      await load();
    } catch (e) {
      setError(messageOf(e));
    } finally {
      setBusy(false);
    }
  };

  if (summary) {
    const figures = [
      { label: 'Questions attempted', value: summary.attempted, tone: 'bg-cream' },
      { label: 'Correct', value: summary.correct, tone: 'bg-sage-soft' },
      { label: 'Wrong', value: summary.wrong, tone: 'bg-gold-soft' },
      { label: 'Score', value: `${summary.score}%`, tone: 'bg-lavender-soft' },
    ];
    const says = summary.attempted === 0 ? 'You hopped through them all. Come back and give them a go!' : summary.score >= 80 ? 'Cheeks full of knowledge. What a run!' : summary.score >= 50 ? 'Solid work. Every answer taught us something!' : 'Every mistake here is a step forward. Proud of you for finishing!';
    return (
      <AppShell title={`${folderName} · ${practice ? 'Done' : 'Complete'}`} stage="right">
        <motion.section initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }} onAnimationComplete={() => confettiBurst(true)} className="card mx-auto flex max-w-3xl flex-col items-center gap-4 px-6 py-8 text-center">
          <div className="px-10 pt-4">
            <HamstarMascot state="celebrating" size={210} />
          </div>
          <h2 className="font-display text-3xl text-[#46291b]">{practice ? (concept ? `Mini-drill done! That was ${folderName}.` : `Practice done! That was ${folderName}.`) : `Great job! You've completed all questions in ${folderName}!`}</h2>
          <p className="hand text-xl">{says}</p>
          <dl className="grid w-full max-w-xl grid-cols-2 gap-3 sm:grid-cols-4">
            {figures.map((f, i) => (
              <motion.div key={f.label} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 + i * 0.08 }} className={`rounded-2xl px-3 py-3 ${f.tone}`}>
                <dd className="text-2xl font-extrabold tabular-nums">{f.value}</dd>
                <dt className="text-xs font-bold text-ink-soft">{f.label}</dt>
              </motion.div>
            ))}
          </dl>
          {summary.skipped > 0 && <p className="text-sm text-ink-soft">{summary.skipped} skipped, not counted in the score.</p>}
          {practice && (
            <div className="mt-2 flex flex-wrap justify-center gap-3">
              <button className="btn btn-primary" disabled={busy} onClick={again}>
                <RotateCcw size={18} /> Go again
              </button>
              <Link to="/learn" className="btn btn-lilac">
                <Compass size={18} /> Back to my folders
              </Link>
            </div>
          )}
          <div className={`mt-2 flex flex-wrap justify-center gap-3 ${practice ? 'hidden' : ''}`}>
            <Link to={`/upload?subject=${encodeURIComponent(folderName)}${doc ? `&parent=${encodeURIComponent(doc.parent)}` : ''}`} className="btn btn-primary">
              <UploadIcon size={18} /> Upload more questions in {folderName}
            </Link>
            <Link to="/learn" className="btn btn-lilac">
              <Compass size={18} /> Try a different subject
            </Link>
          </div>
          <div className={`mt-3 w-full max-w-xl rounded-2xl bg-cream px-4 py-3 ${practice ? 'hidden' : ''}`}>
            <div className="mb-2 text-sm font-bold text-ink-soft">Or stay in {folderName} with another kind of question</div>
            <QuestionTypeSelector compact />
            <button className="mt-3 inline-flex cursor-pointer items-center gap-1.5 text-sm font-bold text-ink-soft underline" disabled={busy} onClick={again}>
              <RotateCcw size={14} /> Go through these {summary.total} again
            </button>
            {error && <p className="mt-2 text-sm text-rose">{error}</p>}
          </div>
        </motion.section>
      </AppShell>
    );
  }

  if (!current) {
    return (
      <AppShell title={folderName}>
        <div className="flex flex-col items-center gap-3 py-10 text-center">
          <HamstarMascot state={writing ? 'processing' : error ? 'thinking' : 'reading'} size={170} />
          <p className={error ? 'max-w-md font-bold' : 'text-ink-soft'}>{error || (writing ? `Writing ${info.label} questions from ${doc?.title ?? folderName} only…` : 'Fetching your question…')}</p>
          {error && (
            <>
              {!practice && <p className="text-sm text-ink-soft">Try another question type, or come back to this one in a moment.</p>}
              {!practice && <QuestionTypeSelector />}
              <div className="flex gap-2">
                <button className="btn btn-primary" onClick={load}>
                  Try again
                </button>
                <Link to="/learn" className="btn btn-ghost">
                  Back to Learn
                </Link>
              </div>
            </>
          )}
        </div>
      </AppShell>
    );
  }

  const { question, number, total } = current;
  const title = practice ? `${folderName} · ${concept ? 'Mini-drill' : 'Practice'} ${number} of ${total}` : `${doc?.title ?? folderName} · Question ${number} of ${total}`;
  const source = practice ? undefined : `${folderName} · questions come only from this document${doc?.kind === 'upload' ? ` (${doc.file_name})` : ''}`;
  // brief and detailed answers come back with what was matched, covered and missed
  const written = !!result && (result.question_type === 'SHORT_ANSWER' || result.question_type === 'LONG_ANSWER');
  const marksNote = result && !isMcq ? `${result.marks_awarded} of ${result.total_marks} mark${result.total_marks === 1 ? '' : 's'}` : undefined;

  if (phase === 'wrong' && result) {
    return (
      <AppShell title={title} stage="wrong">
        <div className="mx-auto max-w-4xl">
          {(!isMcq || photoUrl) && (
            <div className="mb-4 flex justify-center">
              <YourAnswer text={isMcq ? `${pick}: ${question.options.find((o) => o.id === pick)?.text ?? ''}` : answer.trim()} photoUrl={photoUrl} />
            </div>
          )}
          <WrongAnswerFlow key={result.attempt_id} attemptId={result.attempt_id} diagnostic={result.diagnostic} marksNote={marksNote} feedback={written ? result : undefined} recurring={result.recurring} inDrill={practice && !!concept} onFinish={next} />
        </div>
      </AppShell>
    );
  }

  if ((phase === 'checking' || phase === 'right') && result) {
    const yours = isMcq ? `${pick}: ${question.options.find((o) => o.id === pick)?.text}` : answer.trim().slice(0, 90);
    return (
      <AppShell title={title} stage={phase} sub={phase === 'checking' ? `You answered ${yours}` : undefined}>
        {phase === 'checking' ? (
          <AnalysisSequence
            steps={CHECKING}
            done="Result ready"
            onDone={() => {
              celebrate(result.unlocked);
              setPhase(result.is_correct ? 'right' : 'wrong');
            }}
          />
        ) : (
          <section className="card flex min-h-[34rem] flex-col items-center justify-center gap-3 px-6 py-8 text-center">
            <div className="px-12 pt-10">
              <HamstarAnimation
                key="right"
                size={270}
                steps={[{ state: 'spinning', ms: 1300 }, { state: 'correct', ms: 0 }]}
                onStep={(i) => {
                  if (i !== 1) return;
                  setLit(true);
                  confettiBurst();
                  if (STREAK_MILESTONES.includes(result.current_streak)) setDance(result.current_streak);
                }}
              />
            </div>
            <div className="flex min-h-24 flex-col items-center gap-2" aria-live="polite">
              {lit ? (
                <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="flex flex-col items-center gap-2">
                  <div className="flex items-center gap-3">
                    <span className="font-display text-3xl text-sage-deep">Correct!</span>
                    <RewardAnimation />
                    <TiaraFlight />
                  </div>
                  {marksNote && <span className="font-bold">{marksNote}</span>}
                  <span className="max-w-2xl text-ink-soft">{result.feedback}</span>
                  {(!isMcq || photoUrl) && <YourAnswer text={isMcq ? '' : answer.trim()} photoUrl={photoUrl} />}
                  {written && (
                    <div className="mt-2 w-full max-w-2xl">
                      <StructuredFeedback feedback={result} />
                    </div>
                  )}
                </motion.div>
              ) : (
                <p className="hand text-xl">Spinning it up…</p>
              )}
            </div>
            <button className="btn btn-primary" onClick={next} disabled={!lit}>
              Continue <ArrowRight size={18} />
            </button>
            {dance > 0 && <StreakDance streak={dance} onDone={() => setDance(0)} />}
          </section>
        )}
      </AppShell>
    );
  }

  const append = (text: string) => setAnswer((a) => (a ? `${a.trim()} ${text}` : text));
  return (
    <AppShell title={title} sub={source}>
      <div className="mb-4">
        <div className="mb-1 flex justify-between text-xs font-bold text-ink-soft">
          <span>
            Question {number} of {total}
          </span>
          <span className="tabular-nums">{Math.round((number / total) * 100)}%</span>
        </div>
        <div className="progress-thin" role="progressbar" aria-valuemin={1} aria-valuemax={total} aria-valuenow={number} aria-label={`Question ${number} of ${total}`}>
          <span style={{ width: `${(number / total) * 100}%` }} />
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_19rem]">
        <section className="card flex-col p-5 sm:p-7">
          <div className="eyebrow">
            Question {number} · {typeInfo(question.type as typeof type).label}{/mark/i.test(typeInfo(question.type as typeof type).label) ? '' : ` · ${question.marks} mark${question.marks === 1 ? '' : 's'}`}
          </div>
          <p className={`math mb-5 mt-1 leading-snug font-bold ${question.prompt.length > 110 ? 'text-xl' : 'text-[1.7rem]'}`}>{question.prompt}</p>

          {isMcq ? (
            <MCQOptions question={question} selected={pick} onSelect={setPick} disabled={busy} />
          ) : long ? (
            <>
              <textarea
                className={`field resize-y ${question.type === 'LONG_ANSWER' ? 'min-h-64' : 'min-h-36'}`}
                placeholder={question.type === 'LONG_ANSWER' ? 'Write a detailed answer: explain the idea, give the steps, add an example…' : 'Write a short paragraph…'}
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                disabled={busy}
                aria-label="Your answer"
              />
              <div className="mt-2 flex flex-wrap items-center gap-3">
                <VoiceAnswer onTranscript={append} />
                <span className="ml-auto text-sm tabular-nums text-ink-soft">{answer.trim() ? answer.trim().split(/\s+/).length : 0} words</span>
              </div>
            </>
          ) : (
            <input
              className="field !py-3 text-lg"
              placeholder={question.type === 'FILL_BLANK' ? 'Type what goes in the blank' : 'Type your answer'}
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && check()}
              disabled={busy}
              autoFocus
              aria-label="Your answer"
            />
          )}
          <PhotoAttach file={photo} onChange={setPhoto} disabled={busy} />

          <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
            <button className="btn btn-ghost" disabled={busy} onClick={skip}>
              <SkipForward size={16} /> Skip
            </button>
            <div className="flex items-center gap-3">
              {error && <span className="max-w-sm text-sm text-rose">{error}</span>}
              <button className="btn btn-primary" disabled={!ready || busy} onClick={check}>
                {busy ? 'Checking…' : 'Check my answer'} <ArrowRight size={18} />
              </button>
            </div>
          </div>
        </section>

        {/* companion */}
        <aside className="tile flex flex-col items-center gap-3 text-center">
          <div className="flex h-[12rem] items-end justify-center">
            <HamstarMascot size={170} state={busy ? 'analyzing' : ready ? 'thinking' : isMcq ? 'question' : 'listening'} />
          </div>
          <p className="hand min-h-10 text-[1.1rem] leading-tight" aria-live="polite">
            {ready ? 'Lock it in when you are sure.' : isMcq ? 'Take your time. Pick the option you believe in.' : 'Take your time. Write it in your own words.'}
          </p>
          {!practice && (
            <div className="w-full rounded-xl bg-cream px-3 py-2.5">
              <div className="mb-1.5 text-left text-xs font-bold text-ink-soft">Question type</div>
              <QuestionTypeSelector compact />
            </div>
          )}
          <dl className="grid w-full grid-cols-2 gap-2 text-left text-sm">
            <div className="rounded-xl bg-cream px-3 py-2">
              <dt className="text-xs text-ink-soft" data-tip="Correct answers in a row. 10 earns Perfect Paw Streak.">
                Streak
              </dt>
              <dd className="text-lg font-extrabold tabular-nums">{streak}</dd>
            </div>
            <div className="rounded-xl bg-cream px-3 py-2">
              <dt className="text-xs text-ink-soft" data-tip="How sure HamSTAR is that you understand this folder, from your answers so far.">
                Confidence
              </dt>
              <dd className="text-lg font-extrabold tabular-nums">{confidence === undefined ? '–' : `${confidence}/100`}</dd>
            </div>
          </dl>
          <p className="text-xs text-ink-soft">1 correct question = 1 Tiara. Skipping resets the no-skip count.</p>
        </aside>
      </div>
    </AppShell>
  );
}

/** A mini-drill on one concept (`?concept=`) or a focused run through one document (`?document=`). */
export function Practice() {
  return <Session practice />;
}

/** Reopens a saved mistake: targeted help, then a retest that decides whether it now counts as corrected. */
export function Retry() {
  const { id = '' } = useParams();
  const navigate = useNavigate();
  const refresh = useStore((s) => s.refresh);
  const mistake = useStore((s) => s.mistakes.find((m) => m.id === id));

  return (
    <AppShell title="Retry a past mistake" sub={mistake?.question.prompt}>
      <div className="mx-auto max-w-4xl">
        <RemediationFlow
          mistakeId={id}
          onDone={async () => {
            await refresh().catch(() => {});
            navigate('/mistakes');
          }}
        />
      </div>
    </AppShell>
  );
}
