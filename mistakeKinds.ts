import type { MistakeKind, VerdictKind } from '../api/types';

/** The four kinds of mistake, with the colour and wording used for each everywhere in the app. */
export interface KindInfo {
  label: string;
  /** Solid colour (charts, bars, edges). */
  color: string;
  /** What it means, in one sentence for the student. */
  meaning: string;
  /** Chip and banner styling: a pale wash of the colour with a darker text. */
  chip: string;
}

export const KINDS: Record<Exclude<VerdictKind, 'inconclusive'>, KindInfo> = {
  misconception: {
    label: 'Misconception',
    color: '#ef4444',
    meaning: 'A wrong mental model of the concept: the same faulty rule shows up more than once.',
    chip: 'bg-[#fde2e2] text-[#b91c1c] border-[#f5b5b5]',
  },
  gap_in_understanding: {
    label: 'Gap in understanding',
    color: '#f97316',
    meaning: 'This concept has not been learned yet, so it needs teaching from the start.',
    chip: 'bg-[#ffe8d6] text-[#c2410c] border-[#fbc79e]',
  },
  careless_slip: {
    label: 'Careless slip',
    color: '#eab308',
    meaning: 'You knew it, but a small error slipped in.',
    chip: 'bg-[#fdf3c4] text-[#a16207] border-[#f1d77c]',
  },
  calculation_error: {
    label: 'Calculation error',
    color: '#3b82f6',
    meaning: 'You understood the concept, but an arithmetic or computation step went wrong.',
    chip: 'bg-[#dbe8fe] text-[#1d4ed8] border-[#a9c6f8]',
  },
};

export const INCONCLUSIVE: KindInfo = {
  label: 'Not enough evidence',
  color: '#9ca3af',
  meaning: 'The evidence did not pass 70% for any one cause, so no label was given.',
  chip: 'bg-cream-2 text-ink-soft border-line',
};

/** Names used before the four categories, still found in old records. */
const LEGACY: Record<string, VerdictKind> = { slip: 'careless_slip', unknown: 'gap_in_understanding' };

export const kindOf = (verdict: string | null | undefined): KindInfo => KINDS[(LEGACY[verdict ?? ''] ?? verdict) as keyof typeof KINDS] ?? INCONCLUSIVE;

/** The same four categories as stored codes (the "Looks like this was…" banner uses these). */
export const CODE_TO_KIND: Record<MistakeKind, keyof typeof KINDS> = {
  MISCONCEPTION: 'misconception',
  GAP_IN_UNDERSTANDING: 'gap_in_understanding',
  CARELESS_SLIP: 'careless_slip',
  CALCULATION_ERROR: 'calculation_error',
};
