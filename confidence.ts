/**
 * The confidence colour scale, used for folder, subfolder and document edges, the confidence bars and the
 * right-hand panel's strip, so a score always has the same colour wherever it appears.
 */
export interface Band {
  /** Highest score (inclusive) in this band. */
  upTo: number;
  label: string;
  range: string;
  accent: string;
  /** A pale wash of the colour for card backgrounds in light mode. */
  wash: string;
}

export const SCALE: Band[] = [
  { upTo: 40, label: 'Needs attention', range: '0–40', accent: '#ef4444', wash: '#fdecec' },
  { upTo: 60, label: 'Getting started', range: '41–60', accent: '#f97316', wash: '#fff0e3' },
  { upTo: 75, label: 'Getting there', range: '61–75', accent: '#eab308', wash: '#fdf6d8' },
  { upTo: 90, label: 'Doing well', range: '76–90', accent: '#84cc16', wash: '#f0f8de' },
  { upTo: 100, label: 'Mastered!', range: '91–100', accent: '#22c55e', wash: '#e2f6e8' },
];

/** No answers yet: there is no score to colour. */
export const NOT_STARTED: Band = { upTo: -1, label: 'Not started yet', range: 'no attempts', accent: '#9ca3af', wash: '' };

/** The band a confidence score falls in; grey until there has been at least one answer. */
export function tone(confidence: number | null | undefined, answered = 1): Band {
  if (!answered || confidence == null) return NOT_STARTED;
  return SCALE.find((b) => confidence <= b.upTo) ?? SCALE[SCALE.length - 1];
}
