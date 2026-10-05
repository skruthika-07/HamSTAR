import type { ReactNode } from 'react';

const ACCENT = { lavender: '#dccbf3', sage: '#c8dcae', gold: '#fdeebc', sky: '#cfe3f7' };

/** A question on its own slip of paper, with a marker stroke behind the prompt. */
export function QuestionCard({ accent = 'sky', eyebrow, prompt, children }: { accent?: keyof typeof ACCENT; eyebrow?: ReactNode; prompt: string; children: ReactNode }) {
  return (
    <section className="card p-4 sm:p-5">
      {eyebrow && <div className="eyebrow mb-2 flex flex-wrap items-center gap-2">{eyebrow}</div>}
      <h3 className="math mb-4 text-2xl">
        <span className="brush" style={{ background: ACCENT[accent] }}>
          {prompt}
        </span>
      </h3>
      {children}
    </section>
  );
}
