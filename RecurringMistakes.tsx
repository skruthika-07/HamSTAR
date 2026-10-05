import { ArrowRight, Repeat, TriangleAlert } from 'lucide-react';
import { Link } from 'react-router-dom';
import type { RecurringMistake } from '../api/types';
import { useStore } from '../store/useStore';
import { drillLink } from './FolderTree';

/** Shown the moment a concept goes wrong for the second time (or more). */
export function RecurringWarning({ recurring, showDrill = true }: { recurring: Pick<RecurringMistake, 'concept' | 'count' | 'message'>; showDrill?: boolean }) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-2 rounded-2xl border-[1.5px] border-[#ecc8a0] bg-[#fdeedd] px-4 py-3" role="alert">
      <TriangleAlert size={24} className="shrink-0 text-[#c9701a]" />
      <div className="min-w-0 flex-1 basis-56">
        <div className="font-extrabold">{recurring.message}</div>
        <div className="text-sm text-ink-soft">That is {recurring.count} times now. A few questions on just this idea will sort it out.</div>
      </div>
      {showDrill && (
        <Link to={drillLink(recurring.concept)} className="btn btn-lilac !px-3 !py-1.5 text-sm">
          Start the mini-drill <ArrowRight size={16} />
        </Link>
      )}
    </div>
  );
}

/** Every concept that keeps going wrong, with a drill for each, and the kinds of mistake that repeat. */
export function RecurringMistakes({ limit }: { limit?: number }) {
  const { recurring, patterns } = useStore((s) => s.recurring);
  const shown = limit ? recurring.slice(0, limit) : recurring;
  return (
    <section className="tile">
      <div className="mb-3 flex items-center gap-2">
        <Repeat size={20} className="text-[#c9701a]" />
        <h2>Recurring mistakes</h2>
        {recurring.length > 0 && <span className="chip bg-[#fdeedd] font-bold text-[#a85a12]">{recurring.length}</span>}
      </div>
      {shown.length ? (
        <ul className="space-y-2">
          {shown.map((r) => (
            <li key={r.concept} className="flex flex-wrap items-center gap-x-3 gap-y-2 rounded-xl bg-cream px-3 py-2">
              <div className="min-w-0 flex-1 basis-48">
                <div className="truncate text-sm font-bold">{r.concept}</div>
                <div className="text-xs text-ink-soft">
                  {r.parent} › {r.folder} · {r.count} times · mostly {r.mistake_type.label.toLowerCase()}
                  {r.fixes > 0 && ` · ${r.fixes} of ${r.fixes_needed} right since`}
                </div>
              </div>
              <Link to={drillLink(r.concept)} className="chip bg-lavender-soft font-bold text-lavender-deep hover:bg-lavender">
                Mini-drill
              </Link>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-ink-soft">Nothing keeps tripping you up. If the same idea goes wrong twice, it will show up here with a mini-drill.</p>
      )}
      {patterns.length > 0 && (
        <p className="mt-3 text-xs text-ink-soft">
          Your most common kind of mistake: <b className="text-ink">{patterns[0].label}</b> ({patterns[0].count} times). {patterns[0].about}
        </p>
      )}
    </section>
  );
}
