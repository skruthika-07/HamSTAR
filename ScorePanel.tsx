import { Link } from 'react-router-dom';
import { useStore } from '../store/useStore';
import { HamstarMascot } from './mascot/HamstarMascot';
import { SCALE, tone } from '../data/confidence';


/** Confidence per subfolder (every subject the student has), as worked out by the server from their answers. */
export function useScores() {
  const folders = useStore((s) => s.folders.folders);
  const total = useStore((s) => s.totalConfidence);
  // the document to open for a subfolder is its first one: the weakest
  const topics = folders.flatMap((f) => f.subfolders.map((s) => ({ id: s.documents[0]?.id ?? s.name, name: s.name, parent: f.name, confidence: s.confidence, answered: s.answered })));
  const byTopic = Object.fromEntries(topics.map((t) => [t.id, t.confidence])) as Record<string, number>;
  return { byTopic, total, topics };
}

/** "What to practise next", built by the server from past mistakes. */
export function Recommendations({ limit = 3 }: { limit?: number }) {
  const weak = useStore((s) => s.weakAreas).slice(0, limit);
  if (!weak.length) return <p className="text-sm text-ink-soft">No weak spots stand out right now. Keep answering and I will keep watching.</p>;
  return (
    <ul className="space-y-2">
      {weak.map((w) => (
        <li key={w.id} className="flex items-center gap-3 rounded-xl bg-cream px-3 py-2">
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-bold">{w.name}</div>
            <div className="text-xs text-ink-soft">
              {w.topic_name} · {w.reason}
            </div>
          </div>
          <Link to={`/session/${w.topic}`} className="chip bg-lavender-soft font-bold text-lavender-deep hover:bg-lavender">
            Practise
          </Link>
        </li>
      ))}
    </ul>
  );
}

/** The confidence scale as a strip (each colour as wide as its band), with a marker at the current score. */
export function ScoreBar({ value }: { value: number }) {
  return (
    <div className="relative rounded-full border-2 border-line bg-paper p-1">
      <div className="flex gap-0.5 overflow-hidden rounded-full">
        {SCALE.map((b, i) => (
          <span key={b.accent} className="h-4" style={{ background: b.accent, width: `${b.upTo - (i ? SCALE[i - 1].upTo : 0)}%` }} title={`${b.range}: ${b.label}`} />
        ))}
      </div>
      <span className="absolute top-1/2 h-6 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-ink bg-white transition-[left] duration-700" style={{ left: `${4 + value * 0.92}%` }} aria-hidden />
    </div>
  );
}

/** Right-hand sheet of Learn and Tasks. With a parent folder selected it shows that folder's subfolders. */
export function ScorePanel({ folder }: { folder?: string | null }) {
  const folders = useStore((s) => s.folders.folders);
  const total = useStore((s) => s.totalConfidence);
  const chosen = folders.find((f) => f.name === folder);
  const score = chosen ? chosen.confidence : total;
  const rows = (chosen ? chosen.subfolders : folders).map((r) => ({ label: r.name, value: r.confidence, answered: r.answered }));

  return (
    <>
      <div data-tip="How sure HamSTAR is that you understand, based on the evidence in your answers.">
        <div className="ribbon leading-tight">
          <div className="text-sm font-bold">{chosen ? `${chosen.name} confidence` : 'Total confidence score'}</div>
          <div className="font-display text-3xl text-lavender-deep">{score}/100</div>
        </div>
      </div>

      <ScoreBar value={score} />

      <div className="pennant text-center">
        <h2 className="caps px-2 text-sm">{chosen ? 'Subfolder wise' : 'Folder wise'} confidence</h2>
        <ul className="mt-3 space-y-2 text-left text-sm">
          {rows.map((r) => (
            <li key={r.label}>
              <div className="flex items-baseline justify-between gap-2 leading-tight">
                <span>{r.label}</span>
                <span className="font-bold tabular-nums text-sky-deep">{r.value}</span>
              </div>
              <div className="bar mt-1 !bg-white/70">
                <span style={{ width: `${r.value}%`, background: tone(r.value, r.answered).accent }} />
              </div>
            </li>
          ))}
        </ul>
        <div className="mt-3 flex justify-center">
          <HamstarMascot state={score >= 70 ? 'confident' : 'reading'} size={120} />
        </div>
      </div>
    </>
  );
}
