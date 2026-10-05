import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { AppShell } from '../components/layout/AppShell';
import { HamstarMascot } from '../components/mascot/HamstarMascot';
import type { MistakeStatus, VerdictKind } from '../api/types';
import { PastMistakeCard, STATUS_LABEL } from '../components/PastMistakeCard';
import { Recommendations } from '../components/ScorePanel';
import { useFolderName } from '../data/topics';
import { useStore } from '../store/useStore';
import { INCONCLUSIVE, KINDS, type KindInfo } from '../data/mistakeKinds';

// the four kinds of mistake (and the undecided ones), each in its own colour
const PIE: { kind: VerdictKind; label: string; color: string }[] = [
  ...(Object.entries(KINDS) as [VerdictKind, KindInfo][]).map(([kind, k]) => ({ kind, label: k.label, color: k.color })),
  { kind: 'inconclusive', label: INCONCLUSIVE.label, color: INCONCLUSIVE.color },
];

const FILTERS: ('ALL' | MistakeStatus)[] = ['ALL', 'NEEDS_REVIEW', 'MISCONCEPTION_IDENTIFIED', 'GAP_IDENTIFIED', 'SLIP_IDENTIFIED', 'CALCULATION_IDENTIFIED', 'CORRECTED'];

function Pie({ parts }: { parts: { label: string; value: number; color: string }[] }) {
  const total = parts.reduce((s, p) => s + p.value, 0) || 1;
  let a = -Math.PI / 2;
  return (
    <div className="flex items-center gap-3">
      <svg viewBox="-52 -52 104 104" className="w-24 shrink-0" role="img" aria-label="Mistakes by cause">
        {parts
          .filter((p) => p.value)
          .map((p) => {
            const b = a + (p.value / total) * Math.PI * 2;
            const d = p.value === total ? 'M0,-48 A48,48 0 1 1 -0.01,-48 Z' : `M0,0 L${48 * Math.cos(a)},${48 * Math.sin(a)} A48,48 0 ${b - a > Math.PI ? 1 : 0} 1 ${48 * Math.cos(b)},${48 * Math.sin(b)} Z`;
            a = b;
            return <path key={p.label} d={d} fill={p.color} stroke="#fbf3e2" strokeWidth="2" strokeLinejoin="round" />;
          })}
      </svg>
      <ul className="space-y-1 text-sm leading-tight">
        {parts
          .filter((p) => p.value)
          .map((p) => (
            <li key={p.label} className="flex items-center gap-1.5">
              <span className="h-3 w-3 shrink-0 rounded-full" style={{ background: p.color }} />
              {p.label} · {p.value}
            </li>
          ))}
      </ul>
    </div>
  );
}

export default function Mistakes() {
  const mistakes = useStore((s) => s.mistakes);
  const corrected = useStore((s) => s.stats.mistakesCorrected);
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>('ALL');
  // the list is fetched fresh each time the page opens, so a mistake from a moment ago is already here
  const refresh = useStore((s) => s.refresh);
  useEffect(() => {
    refresh().catch(() => {});
  }, [refresh]);
  const folderName = useFolderName();
  const recent = mistakes; // newest first, as the server sends them
  const shown = recent.filter((m) => filter === 'ALL' || m.status === filter);

  return (
    <AppShell
      title="Past Mistakes"
      sub="Learn from today, do better tomorrow."
      aside={
        <>
          <div className="flex items-end gap-2">
            <HamstarMascot state="investigating" size={96} />
            <p className="hand mb-3 text-[1.1rem] leading-tight text-lavender-deep">Mistakes are proof that you are trying. Keep going!</p>
          </div>
          <section className="tile">
            <h2 className="mb-3 text-base">What caused them</h2>
            {recent.length ? <Pie parts={PIE.map((k) => ({ label: k.label, color: k.color, value: recent.filter((m) => m.verdict === k.kind).length }))} /> : <p className="text-sm text-ink-soft">Nothing to chart yet.</p>}
            <div className="mt-3 flex flex-wrap gap-2 text-xs">
              {[...new Set(recent.map((m) => m.topic))].map((t) => (
                <span key={t} className="chip bg-cream-2">
                  {folderName(t)} · {recent.filter((m) => m.topic === t).length}
                </span>
              ))}
            </div>
          </section>
          <section className="tile">
            <h2 className="mb-1 text-base">Practise next</h2>
            <p className="mb-3 text-xs text-ink-soft">Picked from the patterns in your mistakes.</p>
            <Recommendations />
          </section>
          <section className="tile">
            <div className="flex items-baseline justify-between text-sm">
              <span className="font-bold">Mistake Master</span>
              <span className="tabular-nums text-ink-soft">{Math.min(corrected, 50)} / 50 corrected</span>
            </div>
            <div className="bar mt-1.5">
              <span className="bg-lavender-deep" style={{ width: `${Math.min(100, corrected * 2)}%` }} />
            </div>
          </section>
        </>
      }
    >
      <div className="mb-4 flex flex-wrap gap-2" role="tablist" aria-label="Filter by status">
        {FILTERS.map((f) => {
          const n = f === 'ALL' ? recent.length : recent.filter((m) => m.status === f).length;
          return (
            <button key={f} role="tab" aria-selected={filter === f} onClick={() => setFilter(f)} className={`chip cursor-pointer !px-3 !py-1 font-bold transition ${filter === f ? 'bg-ink text-cream' : 'bg-cream-2 text-ink-soft hover:bg-line'}`}>
              {f === 'ALL' ? 'All' : STATUS_LABEL[f]} · {n}
            </button>
          );
        })}
      </div>

      {shown.length ? (
        <div className="space-y-3">
          {shown.map((m) => (
            <PastMistakeCard key={m.id} mistake={m} />
          ))}
        </div>
      ) : (
        <div className="flex flex-col items-center gap-2 py-10 text-center">
          <HamstarMascot state="reading" size={150} />
          <p className="font-bold">{recent.length ? 'Nothing with this status.' : 'No mistakes saved yet.'}</p>
          <p className="max-w-sm text-sm text-ink-soft">When an answer goes wrong, I work out why and keep the record here so you can retry it.</p>
          <Link to="/learn" className="btn btn-primary mt-2">
            Start learning
          </Link>
        </div>
      )}
    </AppShell>
  );
}
