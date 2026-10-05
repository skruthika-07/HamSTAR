import { motion } from 'framer-motion';
import { ArrowRight, BookMarked, Download, FileText, Gauge, GitBranch, HelpCircle, KeyRound, Lightbulb, ListChecks, ListTree, NotebookPen, ScrollText, Trash2, X, Zap } from 'lucide-react';
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { api, messageOf } from '../api/client';
import type { Note, NoteSummary } from '../api/types';
import { AppShell } from '../components/layout/AppShell';
import { MascotSays } from '../components/mascot/HamstarAnimation';
import type { MascotState } from '../components/mascot/HamstarMascot';

const STEPS: { label: string; mascot: MascotState }[] = [
  { label: 'Receiving your file', mascot: 'uploading' },
  { label: 'Reading it: text, headings and definitions', mascot: 'reading' },
  { label: 'Picking out what matters', mascot: 'analyzing' },
  { label: 'Writing your notes', mascot: 'processing' },
];
const WEIGHT_TONE: Record<string, string> = { High: 'bg-[#fbdcd8] text-rose', Medium: 'bg-gold-soft text-gold-deep', Low: 'bg-sage-soft text-sage-deep' };
const day = (t: string | null) => (t ? new Date(t).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) : '');

function Section({ icon, title, tint, children }: { icon: ReactNode; title: string; tint: string; children: ReactNode }) {
  return (
    <section className="break-inside-avoid">
      <h3 className="mb-2 flex items-center gap-2 text-base">
        <span className="tint-chip grid h-8 w-8 shrink-0 place-items-center rounded-xl" style={{ background: tint }}>
          {icon}
        </span>
        {title}
      </h3>
      {children}
    </section>
  );
}

const Bullets = ({ items }: { items: string[] }) => (
  <ul className="list-disc space-y-1 pl-5 leading-relaxed">
    {items.map((p, i) => (
      <li key={i}>{p}</li>
    ))}
  </ul>
);

/** The generated notes, always in the same order of sections. */
function NoteSheet({ note }: { note: Note }) {
  const n = note.content;
  return (
    <div className="space-y-5">
      <Section icon={<ListTree size={17} className="text-oak-deep" />} title="Headings & Subheadings" tint="#efe4cf">
        <ul className="space-y-1.5">
          {n.outline.map((h) => (
            <li key={h.heading}>
              <span className="font-bold">{h.heading}</span>
              {h.subheadings.length > 0 && <span className="text-ink-soft"> — {h.subheadings.join(' · ')}</span>}
            </li>
          ))}
        </ul>
      </Section>
      <Section icon={<BookMarked size={17} className="text-lavender-deep" />} title="Definitions" tint="#e6dcfa">
        <dl className="space-y-1.5">
          {n.definitions.map((d) => (
            <div key={d.term}>
              <dt className="inline font-bold">{d.term}: </dt>
              <dd className="inline">{d.definition}</dd>
            </div>
          ))}
        </dl>
      </Section>
      <Section icon={<ScrollText size={17} className="text-sky-deep" />} title="Summary" tint="#d3e3f5">
        <p className="leading-relaxed">{n.summary}</p>
      </Section>
      <Section icon={<KeyRound size={17} className="text-gold-deep" />} title="Must-Know Keywords" tint="#fdeebc">
        <ul className="grid gap-1.5 sm:grid-cols-2">
          {n.keywords.map((k) => (
            <li key={k.keyword} className="rounded-xl bg-cream px-3 py-1.5 text-sm">
              <b>{k.keyword}</b> <span className="text-ink-soft">— {k.meaning}</span>
            </li>
          ))}
        </ul>
      </Section>
      <Section icon={<ListChecks size={17} className="text-sage-deep" />} title="Key Points" tint="#dcecc9">
        <Bullets items={n.key_points} />
      </Section>
      <Section icon={<Gauge size={17} className="text-rose" />} title="Topic Weightage" tint="#fbdcd8">
        <p>
          <span className={`chip mr-2 font-extrabold ${WEIGHT_TONE[n.weightage.level] ?? WEIGHT_TONE.Medium}`}>{n.weightage.level}</span>
          {n.weightage.reason}
        </p>
      </Section>
      <Section icon={<GitBranch size={17} className="text-oak-deep" />} title="Concept Hierarchy" tint="#efe4cf">
        <ul className="space-y-2">
          {n.hierarchy.map((c) => (
            <li key={c.concept}>
              <span className="font-extrabold">{c.concept}</span>
              <ul className="ml-2 mt-1 space-y-1 border-l-2 border-line pl-4">
                {c.children.map((s) => (
                  <li key={s.concept}>
                    <span className="font-bold">→ {s.concept}</span>
                    {s.details.length > 0 && (
                      <ul className="ml-2 mt-0.5 space-y-0.5 border-l-2 border-line pl-4 text-sm text-ink-soft">
                        {s.details.map((d, i) => (
                          <li key={i}>→ {d}</li>
                        ))}
                      </ul>
                    )}
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
      </Section>
      <Section icon={<Lightbulb size={17} className="text-lavender-deep" />} title="Core Concepts" tint="#e6dcfa">
        <ul className="list-disc space-y-1 pl-5 leading-relaxed">
          {n.core_concepts.map((c) => (
            <li key={c.concept}>
              <b>{c.concept}:</b> {c.explanation}
            </li>
          ))}
        </ul>
      </Section>
      <Section icon={<HelpCircle size={17} className="text-sky-deep" />} title="Potential Questions" tint="#d3e3f5">
        <ol className="list-decimal space-y-1 pl-5 leading-relaxed">
          {n.potential_questions.map((q, i) => (
            <li key={i}>{q}</li>
          ))}
        </ol>
      </Section>
      <Section icon={<Zap size={17} className="text-gold-deep" />} title="Brief Summary" tint="#fdeebc">
        <div className="stitch px-4 py-3" style={{ ['--wash' as string]: '#fbeec5', ['--edge' as string]: '#ecd596' }}>
          <Bullets items={n.brief_summary} />
        </div>
      </Section>
    </div>
  );
}

export default function Notes() {
  const input = useRef<HTMLInputElement>(null);
  const [list, setList] = useState<NoteSummary[]>([]);
  const [note, setNote] = useState<Note | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [working, setWorking] = useState(false);
  const [step, setStep] = useState(0);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');

  const reload = () => api.get<NoteSummary[]>('/api/notes').then(setList);
  useEffect(() => {
    reload().catch((e) => setMessage(messageOf(e)));
  }, []);

  // the steps tick along while the server reads and writes; the last one waits for it
  useEffect(() => {
    if (!working || step >= STEPS.length - 1) return;
    const t = setTimeout(() => setStep(step + 1), 2200);
    return () => clearTimeout(t);
  }, [working, step]);

  const generate = async () => {
    if (!file) return;
    setMessage('');
    setStep(0);
    setWorking(true);
    try {
      const form = new FormData();
      form.append('file', file);
      setNote(await api.post<Note>('/api/notes', form));
      setFile(null);
      await reload();
    } catch (e) {
      setMessage(`I couldn't make notes from that file. ${messageOf(e)}`);
    } finally {
      setWorking(false);
    }
  };

  const open = async (id: string) => {
    setMessage('');
    try {
      setNote(await api.get<Note>(`/api/notes/${id}`));
    } catch (e) {
      setMessage(messageOf(e));
    }
  };

  const remove = async (id: string) => {
    try {
      await api.del(`/api/notes/${id}`);
      if (note?.id === id) setNote(null);
      await reload();
    } catch (e) {
      setMessage(messageOf(e));
    }
  };

  const download = async () => {
    if (!note) return;
    setSaving(true);
    setMessage('');
    try {
      await api.download(`/api/notes/${note.id}/pdf`, `HamSTAR_Notes_${note.title.replace(/[^A-Za-z0-9]+/g, '_').replace(/^_+|_+$/g, '').slice(0, 60) || 'Notes'}.pdf`);
    } catch (e) {
      setMessage(messageOf(e));
    } finally {
      setSaving(false);
    }
  };

  const now = STEPS[Math.min(step, STEPS.length - 1)];
  const mascot: MascotState = working ? now.mascot : message ? 'thinking' : note ? 'confident' : file ? 'uploading' : 'explaining';
  const says = message || (working ? `${now.label}…` : note ? 'Fresh notes, neatly stacked. Download them or read them right here!' : file ? 'Got it. Say the word and I will start scribbling!' : 'Hand me a PDF, an image or a text file and I will turn it into tidy revision notes.');

  const saved = (
    <>
      <h2 className="caps text-center text-sm">Your saved notes</h2>
      {list.length ? (
        <ul className="space-y-2">
          {list.map((n) => (
            <li key={n.id} className={`flex items-center gap-2 rounded-xl px-3 py-2 ${note?.id === n.id ? 'bg-gold-soft' : 'bg-cream'}`}>
              <button className="min-w-0 flex-1 cursor-pointer text-left" onClick={() => open(n.id)}>
                <div className="truncate text-sm font-bold">{n.title}</div>
                <div className="truncate text-xs text-ink-soft">
                  {day(n.created_at)} · {n.file_name}
                </div>
              </button>
              <button aria-label={`Delete notes on ${n.title}`} className="cursor-pointer text-ink-soft hover:text-rose" onClick={() => remove(n.id)}>
                <Trash2 size={15} />
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-center text-sm text-ink-soft">Nothing yet. Every set of notes you make is kept here.</p>
      )}
    </>
  );

  return (
    <AppShell title="Notes" sub="Upload a file and get structured revision notes." aside={saved} stage={note?.id ?? 'new'}>
      <div className="no-print">
        <MascotSays size={130} state={mascot}>
          {says}
        </MascotSays>
      </div>

      {!note && (
        <div
          className={`card no-print mx-auto mt-3 max-w-3xl border-dashed px-6 py-5 ${dragging ? '!border-lavender-deep bg-lavender-soft/60' : ''}`}
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
          <input ref={input} type="file" className="hidden" accept=".pdf,.png,.jpg,.jpeg,.webp,.txt,.md,.docx,.pptx" onChange={(e) => e.target.files?.[0] && setFile(e.target.files[0])} />
          {working ? (
            <ol className="space-y-2 py-2">
              {STEPS.map(({ label }, i) => (
                <li key={label} className="flex items-center gap-3">
                  <span className={`flex h-6 w-6 items-center justify-center rounded-full text-xs ${i < step ? 'bg-sage-deep text-white' : i === step ? 'bg-gold' : 'bg-cream-2 text-ink-soft'}`}>{i + 1}</span>
                  <span className={i <= step ? '' : 'text-ink-soft'}>{label}</span>
                  {i === step && <motion.span className="h-1.5 w-1.5 rounded-full bg-gold-deep" animate={{ opacity: [0.2, 1, 0.2] }} transition={{ duration: 0.8, repeat: Infinity }} />}
                </li>
              ))}
            </ol>
          ) : (
            <>
              <button type="button" onClick={() => input.current?.click()} className="flex w-full cursor-pointer flex-col items-center gap-2 rounded-2xl bg-gold-soft/60 px-4 py-6 transition hover:-translate-y-0.5">
                <NotebookPen size={36} strokeWidth={1.6} className="text-gold-deep" />
                <span className="font-bold">Choose a file, or drop it here</span>
                <span className="text-sm text-ink-soft">PDF, image, text, Word or PowerPoint · up to 20 MB</span>
              </button>
              {file && (
                <div className="mt-3 flex items-center justify-between gap-2 rounded-full bg-cream-2/70 px-4 py-1 text-sm">
                  <span className="flex min-w-0 items-center gap-2">
                    <FileText size={15} className="shrink-0" />
                    <span className="truncate">
                      {file.name} · {(file.size / 1024).toFixed(0)} KB
                    </span>
                  </span>
                  <button aria-label={`Remove ${file.name}`} onClick={() => setFile(null)} className="cursor-pointer">
                    <X size={14} />
                  </button>
                </div>
              )}
              <button className="btn btn-primary mt-4 w-full !text-[1.05rem]" disabled={!file} onClick={generate}>
                Generate my notes <ArrowRight size={18} />
              </button>
            </>
          )}
        </div>
      )}

      {note && (
        <article className="card mt-3 p-5 sm:p-7">
          <header className="mb-5 flex flex-wrap items-start justify-between gap-3 border-b-2 border-dashed border-line pb-4">
            <div className="min-w-0">
              <div className="eyebrow">Notes from {note.file_name}</div>
              <h2 className="font-display text-3xl leading-tight text-[#46291b]">{note.title}</h2>
            </div>
            <div className="no-print flex flex-wrap gap-2">
              <button className="btn btn-ghost" onClick={() => setNote(null)}>
                <NotebookPen size={17} /> New notes
              </button>
              <button className="btn btn-primary" disabled={saving} onClick={download}>
                <Download size={17} /> {saving ? 'Preparing…' : 'Download as PDF'}
              </button>
            </div>
          </header>
          <NoteSheet note={note} />
        </article>
      )}
    </AppShell>
  );
}
