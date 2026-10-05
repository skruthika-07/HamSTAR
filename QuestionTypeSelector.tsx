import type { QuestionType } from '../api/types';
import { useStore } from '../store/useStore';

export const QUESTION_TYPES: { id: QuestionType; label: string; short: string; hint: string; marks: [number, number]; batch: number }[] = [
  { id: 'ONE_WORD', label: '1 Mark', short: '1M', hint: 'One word or a direct answer', marks: [1, 1], batch: 8 },
  { id: 'FILL_BLANK', label: 'Fill in the Blanks', short: 'Blanks', hint: 'Complete the sentence', marks: [1, 2], batch: 8 },
  { id: 'MCQ', label: 'MCQ', short: 'MCQ', hint: 'Multiple choice', marks: [1, 1], batch: 10 },
  { id: 'SHORT_ANSWER', label: 'Answer in Brief', short: 'Brief', hint: '4–8 marks, a short paragraph', marks: [4, 8], batch: 4 },
  { id: 'LONG_ANSWER', label: 'Answer in Detail', short: 'Detail', hint: '12–20 marks, a long detailed answer', marks: [12, 20], batch: 3 },
];

export const typeInfo = (id: QuestionType) => QUESTION_TYPES.find((t) => t.id === id) ?? QUESTION_TYPES[2];

/** Lets the student choose what kind of question to practise. The choice is remembered and applies to every folder. */
export function QuestionTypeSelector({ compact = false }: { compact?: boolean }) {
  const type = useStore((s) => s.questionType);
  const marks = useStore((s) => s.questionMarks);
  const setType = useStore((s) => s.setQuestionType);
  const info = typeInfo(type);
  const [lo, hi] = info.marks;

  return (
    <div className={compact ? 'w-full text-left' : ''}>
      <div className={`flex flex-wrap gap-1.5 ${compact ? '' : 'items-center'}`} role="radiogroup" aria-label="Question type">
        {QUESTION_TYPES.map((t) => (
          <button
            key={t.id}
            role="radio"
            aria-checked={type === t.id}
            data-tip={t.hint}
            onClick={() => setType(t.id)}
            className={`chip cursor-pointer font-bold transition-colors duration-200 ${compact ? '!px-2.5 !py-1 text-xs' : '!px-3.5 !py-1.5 text-sm'} ${type === t.id ? 'bg-ink text-cream' : 'bg-cream-2 text-ink-soft hover:bg-line'}`}
          >
            {compact ? t.short : t.label}
          </button>
        ))}
      </div>
      <div className={`mt-1.5 flex flex-wrap items-center gap-2 text-ink-soft ${compact ? 'text-xs' : 'text-sm'}`}>
        <span>{info.hint}</span>
        {hi > lo && (
          <label className="flex items-center gap-1">
            · marks
            <select className="rounded-full border border-line bg-paper px-2 py-0.5 font-bold text-ink" value={marks[type]} onChange={(e) => setType(type, Number(e.target.value))} aria-label="Marks per question">
              {Array.from({ length: hi - lo + 1 }, (_, i) => lo + i).map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>
    </div>
  );
}
