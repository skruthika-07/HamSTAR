import { CircleCheck, CircleX, FileText, Lightbulb } from 'lucide-react';
import type { ReactNode } from 'react';
import type { WrittenFeedback } from '../api/types';

function Row({ icon, title, tone, children }: { icon: ReactNode; title: string; tone: string; children: ReactNode }) {
  return (
    <div className={`flex gap-3 rounded-xl px-4 py-3 ${tone}`}>
      <span className="mt-0.5 shrink-0">{icon}</span>
      <div className="min-w-0">
        <div className="text-sm font-extrabold">{title}</div>
        <div className="text-[0.95rem] leading-relaxed">{children}</div>
      </div>
    </div>
  );
}

const Chips = ({ items, tone }: { items: string[]; tone: string }) => (
  <div className="mt-1 flex flex-wrap gap-1.5">
    {items.map((k) => (
      <span key={k} className={`chip ${tone}`}>
        {k}
      </span>
    ))}
  </div>
);

/**
 * How a written answer was marked, by ideas rather than wording: the key terms and concepts the student
 * got right, what a complete answer includes, and only the points that were genuinely missing.
 */
export function StructuredFeedback({ feedback, showExplanation = true }: { feedback: WrittenFeedback; showExplanation?: boolean }) {
  const { keywords_matched: keywords = [], concepts_covered: concepts = [], missing_concepts: missed = [], complete_answer: complete } = feedback;
  return (
    <div className="space-y-2 text-left">
      <Row icon={<CircleCheck size={20} className="text-sage-deep" />} title="Keywords matched" tone="bg-sage-soft">
        {keywords.length ? <Chips items={keywords} tone="bg-white/70 text-sage-deep" /> : <span className="text-ink-soft">None of the key terms yet.</span>}
      </Row>
      <Row icon={<Lightbulb size={20} className="text-gold-deep" />} title="Key concepts covered" tone="bg-gold-soft">
        {concepts.length ? (
          <ul className="list-disc pl-5">
            {concepts.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        ) : (
          <span className="text-ink-soft">The main ideas are still to come.</span>
        )}
      </Row>
      {showExplanation && complete && (
        <Row icon={<FileText size={20} className="text-sky-deep" />} title="Explanation" tone="bg-sky/60">
          {complete}
        </Row>
      )}
      {missed.length > 0 && (
        <Row icon={<CircleX size={20} className="text-rose" />} title="Missed points" tone="bg-rose-soft">
          <ul className="list-disc pl-5">
            {missed.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        </Row>
      )}
    </div>
  );
}
