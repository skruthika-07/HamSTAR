/** Shapes returned by the backend (see /docs on the API). Probabilities in Summary are 0..1; confidences are 0..100. */
/** A folder: a starter-bank topic id or any subject name. */
export type TopicId = string;
export type OptionId = 'A' | 'B' | 'C' | 'D';
export type QuestionType = 'ONE_WORD' | 'FILL_BLANK' | 'MCQ' | 'SHORT_ANSWER' | 'LONG_ANSWER';
export type AvatarId = 'graduate' | 'reader' | 'cool' | 'royal' | 'music' | 'sleepy' | 'explorer' | 'coder';
export type BadgeId = 'streak' | 'noskip' | 'mistakes';
/** The four kinds of mistake a diagnosis can name, or 'inconclusive' when none passes 70%. */
export type VerdictKind = 'misconception' | 'careless_slip' | 'gap_in_understanding' | 'calculation_error' | 'inconclusive';
export type MistakeStatus = 'NEEDS_REVIEW' | 'MISCONCEPTION_IDENTIFIED' | 'SLIP_IDENTIFIED' | 'GAP_IDENTIFIED' | 'CALCULATION_IDENTIFIED' | 'CORRECTED';

export interface Option {
  id: OptionId;
  text: string;
  /** Present only once the question has been answered. */
  correct?: boolean;
  reasoning?: string;
}

export interface Question {
  id: string;
  topic: string;
  type: string;
  marks: number;
  prompt: string;
  options: Option[];
  solution?: string;
}

export interface Summary {
  misconception: number;
  /** careless slip */
  slip: number;
  /** gap in understanding */
  unexplained: number;
  calculation?: number;
}

export interface Unlock {
  kind: 'badge' | 'certificate';
  badge?: BadgeId;
}

export interface MisconceptionInfo {
  id: string;
  name: string;
  rule: string;
}

export interface Diagnosis {
  primary: string | null;
  leaning: string;
  secondary: string | null;
  label: string;
  verdict: VerdictKind;
  /** What the category means, in one sentence. */
  meaning?: string | null;
  confidence: number;
  band: string;
  status: string;
  misconception: MisconceptionInfo | null;
}

export interface Prediction {
  option_id: OptionId;
  text: string;
  probability: number;
}

export interface Step {
  question: Question;
  selected: { id: OptionId; text: string };
  is_correct: boolean;
  before: Summary;
  after: Summary;
  gain: number;
  purpose: string;
  outcome: string;
  expected_if_misconception: Prediction | null;
  expected_if_slip: Prediction | null;
  discriminates: boolean;
}

export interface FollowUp {
  session_id: string;
  followup_id?: string;
  question: string | null;
  question_id: string;
  options: Option[];
  purpose: string;
  gain: number;
  source: string;
  /** Sent instead of a question when nothing useful is left to ask. */
  diagnostic?: Diagnostic;
}

export interface Diagnostic {
  session_id: string;
  status: string;
  question: Question;
  selected: { id: OptionId; text: string };
  summary: Summary;
  initial: Summary;
  hypotheses: { kind: string; label: string; confidence: number }[];
  evidence: string[];
  reasoning: string | null;
  reasoning_evidence: { hypothesis: string; label: string; quote: string }[];
  steps: Step[];
  followups_used: number;
  max_followups: number;
  followup: { required: boolean };
  diagnosis: Diagnosis | null;
  feedback: string;
  corrected: boolean;
  mistake_status: MistakeStatus | null;
  unlocked?: Unlock[];
}

/** How a written answer was marked: by the ideas in it, not its wording. */
export interface WrittenFeedback {
  keywords_matched?: string[];
  concepts_covered?: string[];
  missing_concepts?: string[];
  complete_answer?: string;
}

export type MistakeKind = 'CARELESS_SLIP' | 'MISCONCEPTION' | 'GAP_IN_UNDERSTANDING' | 'CALCULATION_ERROR';

export interface EvalResult extends WrittenFeedback {
  attempt_id: string;
  question_type: QuestionType;
  is_correct: boolean;
  marks_awarded: number;
  total_marks: number;
  question: Question;
  feedback: string;
  tiara_awarded: number;
  new_tiara_count: number;
  current_streak: number;
  diagnostic: Diagnostic | null;
  unlocked: Unlock[];
  /** Set when this concept has now gone wrong twice or more. */
  recurring?: { concept: string; count: number; folder: string; message: string } | null;
}

/** The correct answer and an explanation of it. A higher level is simpler, with an everyday example. */
export interface Explanation {
  question: Question;
  correct_answer: { id: OptionId | null; text: string };
  /** The answer always comes in four parts: key terms, core concepts, the full explanation, a line to remember. */
  key_terms: string[];
  core_concepts: string[];
  explanation: string;
  remember: string;
  level: number;
  simpler: boolean;
  /** The kind of mistake the original wrong answer most looks like. Null for follow-up questions. */
  mistake_type: { kind: MistakeKind; label: string; about: string; message: string } | null;
}

/** How a finished set of questions went. */
export interface SetSummary {
  total: number;
  attempted: number;
  correct: number;
  wrong: number;
  skipped: number;
  score: number;
}

export interface NextQuestion {
  /** True when every question in the set has been done; `summary` is then present and `question` is not. */
  completed?: boolean;
  summary?: SetSummary;
  question: Question;
  number: number;
  total: number;
  folder: string;
  /** The one document these questions were written from. */
  document?: { id: string; title: string; file_name: string | null };
}

/** A follow-up on the same concept, for a wrong written answer. */
export interface ConceptFollowUp {
  attempt_id: string;
  question: Question;
  number: number;
  max: number;
}

export interface ConceptFollowUpResult {
  question: Question;
  is_correct: boolean;
  recovered: boolean;
  can_try_another: boolean;
}

export interface Help {
  kind: 'targeted' | 'worked_solution';
  misconception: (MisconceptionInfo & { explanation: string[]; worked_example: string }) | null;
  question: string;
  your_answer: { id: OptionId; text: string; reasoning: string };
  correct_answer: { id: OptionId; text: string };
  solution: string;
}

export interface RetryStep {
  mistake_id: string;
  help: Help;
  question: Question;
  retry_number: number;
  max_retries: number;
}

export interface RetryResult {
  question: Question;
  selected_option: OptionId;
  is_correct: boolean;
  understanding: number;
  corrected: boolean;
  can_retry_again: boolean;
  mistake_status: MistakeStatus;
  unlocked: Unlock[];
}

export interface Mistake {
  id: string;
  created_at: string;
  topic: string;
  question: Question;
  selected: { id: OptionId; text: string; reasoning: string };
  correct: { id: OptionId; text: string };
  reasoning: string | null;
  verdict: VerdictKind;
  diagnosis_label: string;
  misconception: MisconceptionInfo | null;
  confidence: number;
  initial: Summary;
  final: Summary;
  steps: Step[];
  status: MistakeStatus;
  corrected: boolean;
  understanding: number | null;
  explanation: string;
  improvements: string[];
  what_was_learned: string | null;
  /** What the category means, in one sentence. */
  meaning?: string | null;
}

export interface TopicProgress {
  id: TopicId;
  name: string;
  blurb: string;
  confidence: number;
  question_number: number;
  total_questions: number;
  concepts: { id: string; name: string; confidence: number; suspected: number }[];
}

export interface WeakArea {
  id: string;
  name: string;
  topic: TopicId;
  topic_name: string;
  suspected: number;
  open_mistakes: number;
  reason: string;
}

export interface BadgeView {
  id: BadgeId;
  name: string;
  requirement: string;
  target: number;
  progress: number;
  unlocked: boolean;
  unlocked_at: string | null;
}

export interface CertificateView {
  unlocked: boolean;
  target: number;
  tiara: number;
  to_go: number;
  id: string | null;
  unlocked_at: string | null;
  share_token: string | null;
}

export interface Material {
  id: string;
  title: string;
  file_name: string;
  file_type: string;
  topic: TopicId | null;
  /** Any subject; "General" until one is detected or chosen. */
  subject: string;
  subject_detected: boolean;
  /** The parent folder the subject sits in, e.g. Science. */
  parent: string;
  processing_status: 'PENDING' | 'PROCESSED' | 'FAILED';
  processing_error?: string | null;
  question_count: number;
  question_number?: number;
  answered?: number;
  correct?: number;
  accuracy?: number | null;
}

export interface UserView {
  id: string;
  name: string;
  email: string;
  role: string;
  avatar: AvatarId;
}

export interface Dashboard {
  user: UserView;
  tiara: { count: number; target: number; to_go: number };
  streak: { current: number; longest: number; no_skip: number };
  stats: { answered: number; correct: number; skipped: number; mistakes_corrected: number; accuracy: number };
  progress: { total_confidence: number; topics: TopicProgress[] };
  recent_activity: { at: string; text: string }[];
  badges: BadgeView[];
  certificate: CertificateView;
  recommendations: { reason: string; weak_areas: WeakArea[] };
  materials: Material[];
  folders: FolderTree;
  recurring: RecurringSummary;
}

/** One document in a subfolder: an upload, or the starter set that comes with HamSTAR. */
export interface FolderDoc {
  /** What to open: a starter folder id, or "material:<id>". */
  id: string;
  kind: 'starter' | 'upload';
  material_id: string | null;
  title: string;
  file_name: string;
  subject: string;
  parent: string;
  subject_detected: boolean;
  processing_status: 'PENDING' | 'PROCESSED' | 'FAILED';
  processing_error: string | null;
  question_count: number;
  answered: number;
  correct: number;
  /** Per cent of answered questions that were right; null before the first answer. */
  score: number | null;
  confidence: number;
  weak: boolean;
  weak_concepts: { concept: string; count: number }[];
  /** Score compared with the student's average across all documents. */
  vs_average: number | null;
}

export interface Subfolder {
  name: string;
  confidence: number;
  answered: number;
  document_count: number;
  weak: boolean;
  /** Weakest first. */
  documents: FolderDoc[];
}

export interface ParentFolder {
  name: string;
  confidence: number;
  answered: number;
  document_count: number;
  weakest: { subfolder: string; confidence: number; document: string } | null;
  subfolders: Subfolder[];
}

export interface FolderTree {
  folders: ParentFolder[];
  total_confidence: number;
  average_score: number | null;
  /** Parent folders and the subfolders that usually go in them, for the upload form. */
  suggestions: { name: string; subfolders: string[] }[];
  /** Starter sets the student has deleted from their folders (they can be brought back). */
  hidden_starters?: number;
}

export interface RecurringMistake {
  concept: string;
  count: number;
  folder: string;
  parent: string;
  mistake_type: { kind: MistakeKind; label: string };
  fixes: number;
  fixes_needed: number;
  message: string;
}

export interface RecurringSummary {
  recurring: RecurringMistake[];
  patterns: { kind: MistakeKind; label: string; about: string; count: number }[];
  logged: number;
}

/** A focused set of questions: a mini-drill on one concept, or one document. */
export interface PracticeSet {
  kind: 'concept' | 'document';
  title: string;
  folder: string;
  questions: Question[];
}

export interface NoteSummary {
  id: string;
  title: string;
  file_name: string;
  created_at: string | null;
  weightage: string | null;
}

export interface Note extends NoteSummary {
  markdown: string;
  content: {
    title: string;
    outline: { heading: string; subheadings: string[] }[];
    definitions: { term: string; definition: string }[];
    summary: string;
    keywords: { keyword: string; meaning: string }[];
    key_points: string[];
    weightage: { level: string; reason: string };
    hierarchy: { concept: string; children: { concept: string; details: string[] }[] }[];
    core_concepts: { concept: string; explanation: string }[];
    potential_questions: string[];
    brief_summary: string[];
  };
}

export interface PolicyResult {
  policy: 'targeted' | 'random' | 'none';
  precision: number;
  recall: number;
  f1: number;
  true_positives: number;
  predicted_misconception: number;
  misconception_cases: number;
  slip_cases: number;
  slips_overdiagnosed: number;
  slip_false_positive_rate: number;
  decided_rate: number;
  accuracy_when_decided: number;
  avg_follow_ups: number;
  avg_gain: number;
  calibration: { expected_calibration_error: number };
  followup_discrimination: { pattern_repeated_by_misconception_students: number; pattern_repeated_by_slip_students: number };
}

export interface EvalCase {
  name: string;
  actual_cause: string;
  description: string;
  question: string;
  selected: string;
  is_correct: boolean;
  student_said: string | null;
  initial?: { misconception: number; slip: number };
  followups: { question: string; response: string; misconception_before: number; misconception_after: number }[];
  diagnosis: string | null;
  diagnosis_label: string;
  confidence: number;
  confidence_meaning: string;
  outcome_correct: boolean;
}

export interface EvaluationRun {
  id: string;
  seed: number;
  students: number;
  policies: PolicyResult[];
  cases: EvalCase[];
}
