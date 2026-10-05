import { FileText, Lightbulb, Link2, Pin } from 'lucide-react';
import type { ReactNode } from 'react';

interface Props {
  keyTerms: string[];
  coreConcepts: string[];
  explanation: string;
  remember: string;
  /** True once "Explain Again" has been used: the full explanation is then the simpler one. */
  simpler?: boolean;
}

function Part({ icon, label, tone, children }: { icon: ReactNode; label: string; tone: string; children: ReactNode }) {
  return (
    <div className="flex gap-3">
      <span className={`mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-xl ${tone}`}>{icon}</span>
      <div className="min-w-0 flex-1">
        <div className="eyebrow mb-1">{label}</div>
        {children}
      </div>
    </div>
  );
}

/** The correct answer, always in the same four parts: key terms, core concepts, full explanation, a line to remember. */
export function StructuredAnswer({ keyTerms, coreConcepts, explanation, remember, simpler }: Props) {
  return (
    <div className="space-y-4">
      {keyTerms.length > 0 && (
        <Part icon={<Pin size={17} />} label="Key terms" tone="bg-gold-soft text-gold-deep">
          <ul className="flex flex-wrap gap-1.5">
            {keyTerms.map((t) => (
              <li key={t} className="chip math bg-gold-soft !py-1 font-bold text-ink">
                {t}
              </li>
            ))}
          </ul>
        </Part>
      )}
      {coreConcepts.length > 0 && (
        <Part icon={<Lightbulb size={17} />} label="Core concepts" tone="bg-lavender-soft text-lavender-deep">
          <ul className="list-disc space-y-1 pl-5 leading-relaxed">
            {coreConcepts.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        </Part>
      )}
      <Part icon={<FileText size={17} />} label={simpler ? 'Full explanation, in simpler words' : 'Full explanation'} tone="bg-sky text-sky-deep">
        <p className="text-[1.05rem] leading-relaxed">{explanation}</p>
      </Part>
      {remember && (
        <Part icon={<Link2 size={17} />} label="Remember" tone="bg-sage-soft text-sage-deep">
          <p className="hand text-[1.15rem] leading-snug">{remember}</p>
        </Part>
      )}
    </div>
  );
}
