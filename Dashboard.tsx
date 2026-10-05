import { motion } from 'framer-motion';
import { ArrowRight, CircleCheck, Crown, Flame, MessageCircleQuestion, Wrench } from 'lucide-react';
import { useEffect, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { verdictLabel } from '../components/diagnosis/DiagnosisCard';
import { AppShell } from '../components/layout/AppShell';
import { HamstarMascot } from '../components/mascot/HamstarMascot';
import { tone } from '../data/confidence';
import { RecurringMistakes } from '../components/RecurringMistakes';
import { Recommendations, useScores } from '../components/ScorePanel';
import { TIARA_FOR_CERTIFICATE, useStore } from '../store/useStore';

function Stat({ icon, label, value, note, tint, tip }: { icon: ReactNode; label: string; value: ReactNode; note?: string; tint: string; tip: string }) {
  return (
    <div className="tile flex items-center gap-3 max-sm:!p-2.5" data-tip={tip}>
      <span className="tint-chip flex h-11 w-11 shrink-0 items-center justify-center rounded-xl" style={{ background: tint }}>
        {icon}
      </span>
      <div className="min-w-0">
        <div className="text-2xl leading-none font-extrabold tabular-nums">{value}</div>
        <div className="mt-1 truncate text-xs font-bold">{label}</div>
        <div className="truncate text-xs text-ink-soft">{note ?? ' '}</div>
      </div>
    </div>
  );
}

const day = (t: string) => new Date(t).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });

export default function Dashboard() {
  // every figure here is computed by the server and loaded with the dashboard
  const { profile, stats, mistakes, activity, refresh } = useStore();
  useEffect(() => {
    refresh().catch(() => {});
  }, [refresh]);
  // every subfolder the student has, starter or uploaded
  const { topics } = useScores();
  const toGo = Math.max(0, TIARA_FOR_CERTIFICATE - stats.tiara);
  const share = Math.min(1, stats.tiara / TIARA_FOR_CERTIFICATE);
  const accuracy = stats.answered ? Math.round((stats.correct / stats.answered) * 100) : 0;
  const weakest = [...topics].sort((a, b) => a.confidence - b.confidence)[0];

  return (
    <AppShell title="My Dashboard" sub={`Welcome back, ${profile.name}.`}>
      <div className="grid gap-3 lg:grid-cols-12 [&>*]:min-w-0">
        {/* welcome */}
        <section className="stitch flex items-center gap-4 px-5 py-4 max-sm:flex-col max-sm:text-center lg:col-span-8" style={{ ['--wash' as string]: '#fbeec5', ['--edge' as string]: '#ecd596' }}>
          <HamstarMascot state="welcome" size={150} />
          <div className="min-w-0">
            <p className="font-display text-[clamp(1.4rem,2.3vw,2rem)] leading-tight text-[#46291b]">Hop in! Your learning adventure awaits!</p>
            <p className="mt-1 text-ink-soft">
              {weakest ? (
                <>
                  Next up: <b className="text-ink">{weakest.name}</b>, your lowest confidence at {weakest.confidence}/100.
                </>
              ) : (
                'Pick a folder and answer your first question.'
              )}
            </p>
            <Link to={weakest ? `/session/${weakest.id}` : '/learn'} className="btn btn-primary mt-3">
              Continue learning <ArrowRight size={18} />
            </Link>
          </div>
        </section>

        {/* certificate progress */}
        <section className="tile flex items-center gap-4 lg:col-span-4">
          <svg viewBox="0 0 80 80" className="w-24 shrink-0 -rotate-90" role="img" aria-label={`${stats.tiara} of ${TIARA_FOR_CERTIFICATE} Tiara`}>
            <circle cx="40" cy="40" r="33" fill="none" stroke="#f1e4c6" strokeWidth="9" />
            <motion.circle cx="40" cy="40" r="33" fill="none" stroke="#f0b93a" strokeWidth="9" strokeLinecap="round" strokeDasharray={207.3} initial={{ strokeDashoffset: 207.3 }} animate={{ strokeDashoffset: 207.3 * (1 - share) }} transition={{ duration: 1.1, ease: 'easeOut' }} />
          </svg>
          <div className="min-w-0">
            <div className="eyebrow">Certificate</div>
            <div className="text-2xl font-extrabold tabular-nums">
              {Math.min(stats.tiara, TIARA_FOR_CERTIFICATE)}
              <span className="text-base font-semibold text-ink-soft"> / {TIARA_FOR_CERTIFICATE} Tiara</span>
            </div>
            <p className="text-sm text-ink-soft">{toGo ? `${toGo} correct answers to unlock it.` : 'Unlocked. It is on your profile.'}</p>
            <Link to="/profile" className="text-sm font-bold text-lavender-deep underline-offset-4 hover:underline">
              View on profile
            </Link>
          </div>
        </section>

        {/* numbers */}
        <div className="grid grid-cols-2 gap-3 md:grid-cols-5 lg:col-span-12 [&>*]:min-w-0">
          <Stat icon={<Crown size={22} className="text-gold-deep" />} tint="#fdeebc" tip="1 correct question = 1 Tiara" label="Tiara" value={stats.tiara} note="1 per correct" />
          <Stat icon={<MessageCircleQuestion size={22} className="text-sky-deep" />} tint="#d3e3f5" tip="Every question you have submitted an answer to" label="Questions answered" value={stats.answered} />
          <Stat icon={<CircleCheck size={22} className="text-sage-deep" />} tint="#dcecc9" tip="Answered correctly on the first try" label="Correct answers" value={stats.correct} note={`${accuracy}%`} />
          <Stat icon={<Wrench size={22} className="text-lavender-deep" />} tint="#e6dcfa" tip="Counted only after a retry shows understanding above 70%" label="Mistakes corrected" value={stats.mistakesCorrected} />
          <Stat icon={<Flame size={22} className="text-rose" />} tint="#fbdcd8" tip="Correct answers in a row" label="Current streak" value={stats.streak} note={`best ${stats.bestStreak}`} />
        </div>

        {/* progress by subject */}
        <section className="tile lg:col-span-4">
          <h2 className="mb-3">Learning progress</h2>
          <ul className="space-y-3">
            {topics.map((t) => (
              <li key={t.id}>
                <div className="flex items-baseline justify-between text-sm">
                  <Link to={`/session/${t.id}`} className="font-bold hover:underline">
                    {t.name}
                  </Link>
                  <span className="tabular-nums text-ink-soft">{t.confidence}/100 confidence</span>
                </div>
                <div className="bar mt-1">
                  <motion.span style={{ background: tone(t.confidence, t.answered).accent }} initial={{ width: 0 }} animate={{ width: `${t.confidence}%` }} transition={{ duration: 0.9 }} />
                </div>
              </li>
            ))}
          </ul>
          <h3 className="mb-2 mt-4 text-sm">Practise next</h3>
          <Recommendations limit={2} />
        </section>

        {/* recent mistakes */}
        <section className="tile lg:col-span-4">
          <div className="mb-3 flex items-baseline justify-between">
            <h2>Recent mistakes</h2>
            <Link to="/mistakes" className="text-sm font-bold text-lavender-deep hover:underline">
              See all
            </Link>
          </div>
          {mistakes.length ? (
            <ul className="space-y-2">
              {mistakes.slice(0, 4).map((m) => (
                <li key={m.id} className="flex items-center gap-3 rounded-xl bg-cream px-3 py-2">
                  <div className="min-w-0 flex-1">
                    <div className="math truncate text-sm font-bold">{m.question.prompt}</div>
                    <div className="text-xs text-ink-soft">
                      {verdictLabel(m.verdict)} · {Math.round(m.confidence)}% sure
                    </div>
                  </div>
                  <span className={`chip font-bold ${m.corrected ? 'bg-sage-soft text-sage-deep' : 'bg-gold-soft text-gold-deep'}`}>{m.corrected ? 'Corrected' : 'Retry'}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-ink-soft">No mistakes saved yet. They will show up here with what caused them.</p>
          )}
        </section>

        {/* activity */}
        <section className="tile lg:col-span-4">
          <h2 className="mb-3">Recent activity</h2>
          {activity.length ? (
            <ol className="space-y-2.5 border-l-2 border-line pl-4">
              {activity.map((a, i) => (
                <li key={i} className="relative text-sm">
                  <span className="absolute -left-[1.4rem] top-1.5 h-2.5 w-2.5 rounded-full bg-gold" />
                  <span className="math line-clamp-1">{a.text}</span>
                  <span className="text-xs text-ink-soft">{day(a.at)}</span>
                </li>
              ))}
            </ol>
          ) : (
            <p className="text-sm text-ink-soft">Nothing yet. Answer your first question to get going.</p>
          )}
        </section>

        {/* recurring mistakes */}
        <div className="lg:col-span-12">
          <RecurringMistakes />
        </div>
      </div>
    </AppShell>
  );
}
