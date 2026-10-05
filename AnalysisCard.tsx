import { Lightbulb } from 'lucide-react';
import type { Help } from '../../api/types';

/** Targeted help: addresses the specific faulty rule, or walks through the solution when no rule was identified. */
export function AnalysisCard({ help }: { help: Help }) {
  const m = help.misconception;
  return (
    <section className="card p-5 sm:p-6">
      <div className="mb-4 flex items-center gap-3">
        <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-gold-soft text-gold-deep">
          <Lightbulb size={20} />
        </span>
        <div>
          <div className="eyebrow">{m ? 'Targeted explanation' : 'Worked solution'}</div>
          <h3 className="math text-lg font-semibold">{m ? m.name : help.question}</h3>
        </div>
      </div>

      <div className="mb-4 grid gap-2 sm:grid-cols-2">
        <div className="rounded-xl bg-rose-soft px-3.5 py-2.5 text-sm">
          <div className="eyebrow mb-0.5 text-rose">Your answer</div>
          <div className="math text-lg font-semibold">{help.your_answer.text}</div>
          <div className="text-ink-soft">{help.your_answer.reasoning}</div>
        </div>
        <div className="rounded-xl bg-sage-soft px-3.5 py-2.5 text-sm">
          <div className="eyebrow mb-0.5 text-sage-deep">Correct answer</div>
          <div className="math text-lg font-semibold">{help.correct_answer.text}</div>
          <div className="text-ink-soft">{help.solution}</div>
        </div>
      </div>

      {m && (
        <>
          <ol className="space-y-2.5">
            {m.explanation.map((line, i) => (
              <li key={i} className="flex gap-3 text-[0.95rem] leading-relaxed">
                <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-ink text-xs font-bold text-cream">{i + 1}</span>
                {line}
              </li>
            ))}
          </ol>
          {m.worked_example && <div className="math mt-4 rounded-xl border border-dashed border-oak bg-cream px-4 py-3 text-center text-lg">{m.worked_example}</div>}
        </>
      )}
    </section>
  );
}
