import { ArrowRight, FileText, Image, Presentation, StickyNote, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { api, messageOf } from '../api/client';
import type { Material } from '../api/types';
import { useStore } from '../store/useStore';
import { Sprig } from './layout/AppShell';
import { typeInfo } from './QuestionTypeSelector';
import { MascotSays } from './mascot/HamstarAnimation';
import type { MascotState } from './mascot/HamstarMascot';

const KINDS: { label: string; icon: typeof FileText; tint: string; ink: string; accept: string }[] = [
  { label: 'PDFs', icon: FileText, tint: '#f9d3d6', ink: '#e04848', accept: '.pdf' },
  { label: 'PPTs', icon: Presentation, tint: '#cfe0f5', ink: '#3f6fd6', accept: '.pptx' },
  { label: 'Images', icon: Image, tint: '#d3e8c6', ink: '#4f9a4a', accept: 'image/png,image/jpeg,image/webp' },
  { label: 'Notes', icon: StickyNote, tint: '#fbe6b0', ink: '#c98a1a', accept: '.txt,.md,.docx' },
];

/** Suggestions only: any subject can be typed. */
export const SUBJECT_IDEAS = ['Mathematics', 'Physics', 'Chemistry', 'Biology', 'Computer Science', 'Object-Oriented Programming', 'Data Structures', 'Calculus', 'Statistics', 'Economics', 'History', 'Geography', 'English'];

const STEPS: { label: string; mascot: MascotState }[] = [
  { label: 'Receiving the document', mascot: 'uploading' },
  { label: 'Opening and reading the pages', mascot: 'reading' },
  { label: 'Working out which folder it belongs in', mascot: 'analyzing' },
  { label: 'Writing the questions', mascot: 'listening' },
  { label: 'Getting the first question ready', mascot: 'processing' },
];

type Stage = 'pick' | 'working' | 'subject' | 'retry';

/**
 * Upload → the server reads the file → the subject is detected (or the student names it) →
 * questions are written from it → off to the first one. Any subject is welcome.
 * `onReady` receives the folder to open: "material:<id>".
 */
export function StudyMaterialUpload({ onReady, initialSubject = '', initialParent = '' }: { onReady: (folder: string) => void; initialSubject?: string; initialParent?: string }) {
  const refresh = useStore((s) => s.refresh);
  const type = useStore((s) => s.questionType);
  const marks = useStore((s) => s.questionMarks[s.questionType]);
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  // filled in already when the student came here to add more to a subject they just finished
  const [subject, setSubject] = useState(initialSubject);
  // the parent folder (Maths, Science, …) the subfolder goes in; worked out from the file when left blank
  const [parent, setParent] = useState(initialParent);
  const parents = useStore((s) => s.folders.suggestions);
  const own = useStore((s) => s.folders.folders);
  const parentNames = [...new Set([...own.map((f) => f.name), ...parents.map((p) => p.name)])];
  const subfolderIdeas = [...new Set([...(own.find((f) => f.name.toLowerCase() === parent.trim().toLowerCase())?.subfolders.map((s) => s.name) ?? []), ...(parents.find((p) => p.name.toLowerCase() === parent.trim().toLowerCase())?.subfolders ?? SUBJECT_IDEAS)])];
  const [dragging, setDragging] = useState(false);
  const [stage, setStage] = useState<Stage>('pick');
  const [step, setStep] = useState(0);
  // how much of the file has been sent, 0 to 1
  const [sent, setSent] = useState(0);
  const [material, setMaterial] = useState<Material | null>(null);
  const [message, setMessage] = useState('');

  const pick = (accept: string) => {
    if (!input.current) return;
    input.current.accept = accept;
    input.current.click();
  };

  // the steps move along on their own while the server works; the last one waits for it
  useEffect(() => {
    if (stage !== 'working' || step >= STEPS.length - 1) return;
    const t = setTimeout(() => setStep(step + 1), 1500);
    return () => clearTimeout(t);
  }, [stage, step]);

  /** Write the questions for a material that has been read, then open its folder. */
  const writeQuestions = async (m: Material) => {
    setStage('working');
    setStep((s) => Math.max(s, 3));
    try {
      // in the question type the student has chosen
      await api.post('/api/questions/generate', { study_material_id: m.id, question_type: type, marks, number_of_questions: typeInfo(type).batch, difficulty: 'medium' });
      await refresh().catch(() => {});
      onReady(`material:${m.id}`);
    } catch (e) {
      await refresh().catch(() => {});
      // the file is kept; only the question-writing needs another go
      setMessage(`Your file is saved under "${m.parent} › ${m.subject}". I couldn't write the questions just now (${messageOf(e)}) Try again in a moment.`);
      setStage('retry');
    }
  };

  const start = async () => {
    if (!file) return;
    setMessage('');
    setStep(0);
    setSent(0);
    setStage('working');
    try {
      const form = new FormData();
      form.append('file', file);
      if (subject.trim()) form.append('subject', subject.trim());
      if (parent.trim()) form.append('parent', parent.trim());
      const m = await api.upload<Material>('/api/study-materials/upload', form, setSent);
      setMaterial(m);
      if (m.processing_status !== 'PROCESSED') {
        await refresh().catch(() => {});
        setMessage(`I couldn't read this file. ${m.processing_error ?? ''} Try a text PDF, Word, PowerPoint, an image or notes.`);
        setStage('pick');
        return;
      }
      if (!m.subject_detected) {
        // not an error: ask instead of guessing
        if (m.parent !== 'Other') setParent(m.parent);
        setMessage("We couldn't detect the subject — please select it manually.");
        setStage('subject');
        return;
      }
      await writeQuestions(m);
    } catch (e) {
      setMessage(messageOf(e));
      setStage('pick');
    }
  };

  /** The student names the subject (or accepts "General"), then the questions are written. */
  const confirmSubject = async (name: string) => {
    if (!material) return;
    setMessage('');
    try {
      const m = name.trim() ? await api.patch<Material>(`/api/study-materials/${material.id}`, { subject: name.trim(), parent: parent.trim() || undefined }) : material;
      setMaterial(m);
      await writeQuestions(m);
    } catch (e) {
      setMessage(messageOf(e));
    }
  };

  const now = STEPS[Math.min(step, STEPS.length - 1)];
  // sending the file is the first 40%; reading it and writing the questions fill the rest, step by step
  const percent = Math.round(Math.min(sent, 1) * 40 + (sent >= 1 ? (Math.min(step, STEPS.length - 1) / (STEPS.length - 1)) * 55 : 0));
  const mascot: MascotState = stage === 'working' ? now.mascot : stage === 'subject' ? 'question' : stage === 'retry' ? 'thinking' : message ? 'thinking' : file ? 'uploading' : 'explaining';
  const says = message || (stage === 'working' ? `${now.label}…` : file ? 'Got it. I will take care of the reading!' : 'Upload your study material and I will prepare questions just for you! Any subject works.');

  return (
    <>
      <MascotSays size={150} state={mascot}>
        {says}
      </MascotSays>
      <div
        className={`card mt-3 border-dashed px-6 pb-4 pt-5 ${dragging ? '!border-lavender-deep bg-lavender-soft/60' : ''}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          if (e.dataTransfer.files[0]) setFile(e.dataTransfer.files[0]);
        }}
      >
        <h2 className="mb-4 text-center text-xl">Upload your study material</h2>
        <input ref={input} type="file" className="hidden" onChange={(e) => e.target.files?.[0] && setFile(e.target.files[0])} />
        <datalist id="subject-ideas">
          {subfolderIdeas.map((s) => (
            <option key={s} value={s} />
          ))}
        </datalist>
        <datalist id="parent-ideas">
          {parentNames.map((s) => (
            <option key={s} value={s} />
          ))}
        </datalist>

        {stage === 'pick' && (
          <>
            <div className="grid grid-cols-4 gap-3">
              {KINDS.map(({ label, icon: Icon, tint, ink, accept }) => (
                <button key={label} type="button" onClick={() => pick(accept)} className="tint-chip flex cursor-pointer flex-col items-center gap-1 rounded-2xl px-1 py-4 text-sm font-semibold transition hover:-translate-y-0.5" style={{ background: tint }}>
                  <Icon size={32} strokeWidth={1.6} style={{ color: ink }} />
                  {label}
                </button>
              ))}
            </div>

            {file && (
              <div className="mt-3 flex items-center justify-between gap-2 rounded-full bg-cream-2/70 px-4 py-1 text-sm">
                <span className="truncate">
                  {file.name} · {(file.size / 1024).toFixed(0)} KB
                </span>
                <button aria-label={`Remove ${file.name}`} onClick={() => setFile(null)} className="cursor-pointer">
                  <X size={14} />
                </button>
              </div>
            )}

            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <label className="block text-sm">
                <span className="font-bold">Parent folder</span> <span className="text-ink-soft">(optional)</span>
                <input className="field mt-1" list="parent-ideas" placeholder="e.g. Maths, Science, Computer Science…" value={parent} maxLength={80} onChange={(e) => setParent(e.target.value)} />
              </label>
              <label className="block text-sm">
                <span className="font-bold">Subfolder</span> <span className="text-ink-soft">(optional)</span>
                <input className="field mt-1" list="subject-ideas" placeholder="e.g. Algebra, Physics, Data Structures…" value={subject} maxLength={80} onChange={(e) => setSubject(e.target.value)} />
              </label>
            </div>
            <p className="mt-1 text-xs text-ink-soft">Leave them blank and I will work out where it belongs. Several documents can share a subfolder.</p>

            <button className="btn btn-primary mt-4 w-full !text-[1.05rem]" disabled={!file} onClick={start}>
              Start Learning <ArrowRight size={18} />
            </button>
            <p className="mt-3 flex items-center justify-center gap-3 text-sm">
              <span className="text-rose">♥</span> {file ? "I'll take care of the reading!" : 'Pick a file type, or drop a file here. Up to 20 MB.'} <span className="text-rose">♥</span>
              <Sprig className="w-5" />
            </p>
          </>
        )}

        {stage === 'working' && (
          <div className="py-2">
            <div className="mb-1 flex justify-between gap-3 text-sm">
              <span className="font-bold">
                {sent < 1 ? 'Uploading your file' : now.label}
                {step > 2 && material?.subject_detected ? ` · ${material.parent} › ${material.subject}` : ''}
              </span>
              <span className="tabular-nums text-ink-soft">{percent}%</span>
            </div>
            <div className="progress-thin" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent} aria-label="Upload progress">
              <span style={{ width: `${percent}%` }} />
            </div>
          </div>
        )}

        {stage === 'subject' && material && (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              confirmSubject(subject);
            }}
          >
            <p className="mb-2 text-sm text-ink-soft">
              <b className="text-ink">{material.file_name}</b> was read fine. Pick its parent folder and name the subfolder it goes in.
            </p>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="block text-sm font-bold">
                Parent folder
                <input className="field mt-1 font-normal" list="parent-ideas" placeholder="e.g. Science" value={parent} maxLength={80} onChange={(e) => setParent(e.target.value)} />
              </label>
              <label className="block text-sm font-bold">
                Subfolder (new or existing)
                <input className="field mt-1 font-normal" list="subject-ideas" autoFocus placeholder="Type any subtopic, e.g. Thermodynamics" value={subject} maxLength={80} onChange={(e) => setSubject(e.target.value)} aria-label="Subject" />
              </label>
            </div>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {parentNames.slice(0, 7).map((p) => (
                <button key={p} type="button" onClick={() => setParent(p)} className={`chip cursor-pointer !px-3 !py-1 font-semibold ${parent === p ? 'bg-lavender-deep text-white' : 'bg-lavender-soft hover:bg-lavender'}`}>
                  {p}
                </button>
              ))}
            </div>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {subfolderIdeas.slice(0, 9).map((s) => (
                <button key={s} type="button" onClick={() => setSubject(s)} className={`chip cursor-pointer !px-3 !py-1 font-semibold ${subject === s ? 'bg-ink text-cream' : 'bg-cream-2 hover:bg-line'}`}>
                  {s}
                </button>
              ))}
            </div>
            <div className="mt-4 flex flex-wrap justify-end gap-2">
              <button type="button" className="btn btn-ghost" onClick={() => confirmSubject('')}>
                Use "General"
              </button>
              <button className="btn btn-primary" disabled={!subject.trim()}>
                Continue <ArrowRight size={18} />
              </button>
            </div>
          </form>
        )}

        {stage === 'retry' && material && (
          <div className="flex flex-wrap justify-end gap-2 py-2">
            <button className="btn btn-ghost" onClick={() => setStage('pick')}>
              Upload something else
            </button>
            <button
              className="btn btn-primary"
              onClick={() => {
                setMessage('');
                writeQuestions(material);
              }}
            >
              Try again <ArrowRight size={18} />
            </button>
          </div>
        )}
      </div>
    </>
  );
}
