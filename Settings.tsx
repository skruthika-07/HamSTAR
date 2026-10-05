import { useEffect, useState, type ReactNode } from 'react';
import { api, messageOf } from '../api/client';
import type { EvaluationRun, PolicyResult } from '../api/types';
import { AppShell } from '../components/layout/AppShell';
import { HamstarMascot } from '../components/mascot/HamstarMascot';
import { useStore } from '../store/useStore';

const pct = (x: number) => `${Math.round(x * 100)}%`;
const STUDENTS = 400;
const POLICY: Record<PolicyResult['policy'], string> = { targeted: 'Targeted follow-up (HamSTAR)', random: 'Random follow-up', none: 'No follow-up' };
const CAUSE: Record<string, string> = { MISCONCEPTION: 'Misconception', CARELESS_SLIP: 'Careless slip', GAP_IN_UNDERSTANDING: 'Gap in understanding', CALCULATION_ERROR: 'Calculation error', MISINTERPRETATION: 'Misread the question (a careless slip)', STRONG_UNDERSTANDING: 'Strong understanding' };

function Metric({ label, value, note }: { label: string; value: ReactNode; note: string }) {
  return (
    <div className="rounded-xl bg-cream px-3 py-2.5">
      <div className="text-2xl leading-none font-extrabold tabular-nums">{value}</div>
      <div className="mt-1 text-sm font-bold">{label}</div>
      <div className="text-xs text-ink-soft">{note}</div>
    </div>
  );
}

/**
 * Evidence for judges that the diagnosis works. The server runs simulated students with a known
 * cause through the same engine real students use; nothing shown here is a fixed number.
 */
function JudgeDemo() {
  const [run, setRun] = useState<EvaluationRun | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const start = async (seed: number) => {
    setBusy(true);
    setError('');
    try {
      setRun(await api.post<EvaluationRun>('/api/evaluation/run', { students: STUDENTS, seed }));
    } catch (e) {
      setError(messageOf(e));
    } finally {
      setBusy(false);
    }
  };

  // show the last run if there is one, otherwise make the first
  useEffect(() => {
    api
      .get<EvaluationRun | null>('/api/evaluation/results')
      .then((last) => (last ? setRun(last) : start(7)))
      .catch((e) => setError(messageOf(e)));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const r = run?.policies[0];
  return (
    <section className="tile">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg">Judge demo</h2>
          <p className="max-w-2xl text-sm text-ink-soft">
            {STUDENTS} simulated students, each given a hidden cause (a misconception, careless slips, or an unmodelled gap), answer the question bank. Every number below is computed on the server by the same engine the student uses.
          </p>
        </div>
        <button className="btn btn-ghost" disabled={busy} onClick={() => start((run?.seed ?? 7) + 1)}>
          {busy ? 'Running…' : 'Run with new students'}
        </button>
      </div>
      {error && <p className="mt-3 text-sm font-semibold text-rose">{error}</p>}

      {!run || !r ? (
        !error && (
          <div className="flex flex-col items-center gap-2 py-8">
            <HamstarMascot state="processing" size={130} />
            <p className="text-sm text-ink-soft">Running the simulated students…</p>
          </div>
        )
      ) : (
        <>
          <div className="mt-4 grid grid-cols-2 gap-2 lg:grid-cols-4">
            <Metric label="Misconception precision" value={pct(r.precision)} note={`${r.true_positives} of ${r.predicted_misconception} labels were right`} />
            <Metric label="Misconception recall" value={pct(r.recall)} note={`of ${r.misconception_cases} true misconception cases`} />
            <Metric label="F1" value={pct(r.f1)} note="balance of precision and recall" />
            <Metric label="Slip false-positive rate" value={pct(r.slip_false_positive_rate)} note={`${r.slips_overdiagnosed} of ${r.slip_cases} slips wrongly called a misconception`} />
            <Metric label="Calibration error" value={pct(r.calibration.expected_calibration_error)} note="gap between stated confidence and accuracy" />
            <Metric
              label="Follow-up discrimination"
              value={`${pct(r.followup_discrimination.pattern_repeated_by_misconception_students)} vs ${pct(r.followup_discrimination.pattern_repeated_by_slip_students)}`}
              note="wrong pattern repeats: misconception vs slip students"
            />
            <Metric label="Decided above 70%" value={pct(r.decided_rate)} note={`${pct(r.accuracy_when_decided)} correct when decided`} />
            <Metric label="Follow-ups needed" value={r.avg_follow_ups.toFixed(2)} note={`${r.avg_gain.toFixed(2)} bits gained per follow-up`} />
          </div>

          <h3 className="mb-2 mt-5 text-sm">Does the targeted follow-up matter?</h3>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[36rem] text-left text-sm">
              <thead className="text-xs text-ink-soft">
                <tr>
                  <th className="py-1 font-semibold">Policy</th>
                  <th className="font-semibold">Precision</th>
                  <th className="font-semibold">Recall</th>
                  <th className="font-semibold">F1</th>
                  <th className="font-semibold">Decided</th>
                  <th className="font-semibold">Slip false positives</th>
                  <th className="font-semibold">Calibration error</th>
                </tr>
              </thead>
              <tbody className="tabular-nums">
                {run.policies.map((x) => (
                  <tr key={x.policy} className={`border-t border-line ${x.policy === 'targeted' ? 'font-bold' : ''}`}>
                    <td className="py-1.5">{POLICY[x.policy]}</td>
                    <td>{pct(x.precision)}</td>
                    <td>{pct(x.recall)}</td>
                    <td>{pct(x.f1)}</td>
                    <td>{pct(x.decided_rate)}</td>
                    <td>
                      {x.slips_overdiagnosed} / {x.slip_cases}
                    </td>
                    <td>{pct(x.calibration.expected_calibration_error)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <h3 className="mb-2 mt-5 text-sm">Five students, one question</h3>
          <div className="grid gap-3 lg:grid-cols-2 2xl:grid-cols-3">
            {run.cases.map((c) => (
              <article key={c.name} className="rounded-xl border-[1.5px] border-line bg-cream p-3 text-sm">
                <div className="flex items-baseline justify-between gap-2">
                  <h4 className="font-extrabold">{c.name}</h4>
                  <span className="chip bg-cream-2 text-xs">Actual cause: {CAUSE[c.actual_cause] ?? c.actual_cause}</span>
                </div>
                <p className="text-xs text-ink-soft">{c.description}</p>
                <dl className="mt-2 space-y-1.5">
                  <div>
                    <dt className="inline text-ink-soft">Question: </dt>
                    <dd className="math inline font-bold">{c.question}</dd>
                  </div>
                  <div>
                    <dt className="inline text-ink-soft">{c.is_correct ? 'Answered: ' : 'Wrong option chosen: '}</dt>
                    <dd className="math inline font-bold">{c.selected}</dd>
                  </div>
                  {c.student_said && (
                    <div>
                      <dt className="inline text-ink-soft">Said: </dt>
                      <dd className="inline italic">"{c.student_said}"</dd>
                    </div>
                  )}
                  {c.initial && (
                    <div>
                      <dt className="inline text-ink-soft">Before any follow-up: </dt>
                      <dd className="inline">
                        misconception {Math.round(c.initial.misconception)}%, slip {Math.round(c.initial.slip)}%
                      </dd>
                    </div>
                  )}
                  {c.followups.map((s, i) => (
                    <div key={i} className="rounded-lg bg-paper px-2.5 py-1.5">
                      <dt className="text-xs text-ink-soft">Follow-up {i + 1}</dt>
                      <dd>
                        <span className="math font-bold">{s.question}</span> → answered <span className="math font-bold">{s.response}</span>
                        <span className="text-ink-soft">
                          {' '}
                          (misconception {Math.round(s.misconception_before)}% → {Math.round(s.misconception_after)}%)
                        </span>
                      </dd>
                    </div>
                  ))}
                  <div>
                    <dt className="inline text-ink-soft">HamSTAR's diagnosis: </dt>
                    <dd className={`inline font-extrabold ${c.outcome_correct ? 'text-sage-deep' : 'text-rose'}`}>
                      {c.diagnosis_label}, {Math.round(c.confidence)}% {c.confidence_meaning === 'understanding' ? 'understanding' : 'confidence'}
                    </dd>
                  </div>
                </dl>
              </article>
            ))}
          </div>
        </>
      )}
    </section>
  );
}

export default function Settings() {
  const profile = useStore((s) => s.profile);
  const signOut = useStore((s) => s.signOut);
  const demo = useStore((s) => s.demo);
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);

  const act = (action: 'load' | 'reset' | 'add_tiara', done: string) => async () => {
    setBusy(true);
    try {
      await demo(action, 50);
      setNote(done);
    } catch (e) {
      setNote(messageOf(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AppShell title="Settings" sub="Your account, the demo data, and the judge demo.">
      <div className="grid gap-3 lg:grid-cols-[1fr_1fr_auto]">
        <section className="tile">
          <h2 className="text-lg">Account</h2>
          <p className="text-sm text-ink-soft">
            Signed in as <b className="text-ink">{profile.name}</b>
            {profile.email && ` (${profile.email})`}. Your progress is saved to your account.
          </p>
          <button className="btn btn-ghost mt-3" onClick={signOut}>
            Sign out
          </button>
        </section>
        <section className="tile">
          <h2 className="text-lg">Demo data</h2>
          <div className="mt-2 flex flex-wrap gap-2">
            <button className="btn btn-ghost" disabled={busy} onClick={act('load', 'Demo history loaded: five diagnosed mistakes and 342 Tiara.')}>
              Load demo history
            </button>
            <button className="btn btn-ghost" disabled={busy} onClick={act('reset', 'Progress cleared.')}>
              Start empty
            </button>
            <button className="btn btn-ghost" disabled={busy} onClick={act('add_tiara', 'Added 50 Tiara for the demo.')}>
              +50 Tiara (demo)
            </button>
          </div>
          <p className="mt-2 min-h-5 text-sm text-sage-deep" aria-live="polite">
            {note}
          </p>
        </section>
        <div className="flex items-end justify-center px-4 max-lg:hidden">
          <HamstarMascot state="settings" size={120} />
        </div>
      </div>
      <div className="mt-3">
        <JudgeDemo />
      </div>
    </AppShell>
  );
}
