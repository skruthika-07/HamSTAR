import { AnimatePresence, motion } from 'framer-motion';
import { ArrowRight, BookOpen, Check, ChevronRight, FileText, Folder, FolderOpen, Info, Pencil, Plus, Sparkles, Trash2, TriangleAlert, Undo2, X } from 'lucide-react';
import { useEffect, useState, type CSSProperties, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { Link, useNavigate } from 'react-router-dom';
import { api, messageOf } from '../api/client';
import type { FolderDoc, FolderTree as Tree, ParentFolder, Subfolder } from '../api/types';
import { useStore } from '../store/useStore';
import { typeInfo } from './QuestionTypeSelector';
import { NOT_STARTED, SCALE, tone } from '../data/confidence';

export const practiceLink = (doc: string) => `/practice?document=${encodeURIComponent(doc)}`;
export const drillLink = (concept: string) => `/practice?concept=${encodeURIComponent(concept)}`;

const tinted = (confidence: number, answered: number): CSSProperties => {
  const t = tone(confidence, answered);
  return { borderLeft: `7px solid ${t.accent}`, ...(t.wash ? { backgroundColor: t.wash } : {}), transition: 'background-color 0.6s, border-color 0.6s' };
};
/** The class that lets dark mode swap the pale wash for a dark card while keeping the coloured edge. */
const tintClass = (answered: number) => `conf-tint${answered ? '' : ' conf-neutral'}`;

/** The key to the folder colours. */
function Legend() {
  const [open, setOpen] = useState(false);
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs">
      <button className="inline-flex cursor-pointer items-center gap-1 font-bold text-ink-soft hover:text-ink" onClick={() => setOpen(!open)} aria-expanded={open} data-tip="Folder colours follow your confidence score">
        <Info size={15} /> What do the folder colours mean?
      </button>
      {open &&
        [...SCALE, NOT_STARTED].map((t) => (
          <span key={t.label} className="inline-flex items-center gap-1.5 rounded-full bg-paper px-2.5 py-1">
            <span className="h-3 w-3 rounded-full" style={{ background: t.accent }} />
            <b>{t.label}</b> <span className="text-ink-soft">{t.range}</span>
          </span>
        ))}
    </div>
  );
}

/** Confidence as a small bar with its number: the same on a parent folder, a subfolder and a document. */
function Confidence({ value, answered }: { value: number; answered: number }) {
  const t = tone(value, answered);
  return (
    <div className="flex items-center gap-2" data-tip={`${t.label}. How sure HamSTAR is that you understand this, from your answers. Brief and detailed answers count for more.`}>
      <div className="bar w-20 !bg-white/70 sm:w-28">
        <span style={{ width: `${value}%`, background: answered ? t.accent : '#e9b23a' }} />
      </div>
      <span className="w-14 text-right text-xs font-bold tabular-nums text-ink-soft">{value}/100</span>
    </div>
  );
}

function Collapse({ open, children }: { open: boolean; children: ReactNode }) {
  return (
    <AnimatePresence initial={false}>
      {open && (
        <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.22, ease: 'easeOut' }} className="overflow-hidden">
          {children}
        </motion.div>
      )}
    </AnimatePresence>
  );
}

/** "Are you sure?" before a folder and everything in it is deleted. */
function ConfirmDelete({ name, busy, error, onCancel, onDelete }: { name: string; busy: boolean; error: string; onCancel: () => void; onDelete: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && !busy && onCancel();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [busy, onCancel]);
  return createPortal(
    <motion.div className="fixed inset-0 z-40 flex items-center justify-center bg-ink/45 p-4" initial={{ opacity: 0 }} animate={{ opacity: 1 }} role="alertdialog" aria-modal="true" aria-labelledby="delete-title" onClick={() => !busy && onCancel()}>
      <motion.div initial={{ scale: 0.9, y: 12 }} animate={{ scale: 1, y: 0 }} className="panel w-full max-w-md p-6 text-center" onClick={(e) => e.stopPropagation()}>
        <span className="mx-auto grid h-14 w-14 place-items-center rounded-full bg-[#fbdcd8] text-rose">
          <Trash2 size={26} />
        </span>
        <h2 id="delete-title" className="mt-3 text-xl leading-snug">
          Are you sure you want to delete {name}?
        </h2>
        <p className="mt-1 text-ink-soft">All documents and questions inside will also be deleted.</p>
        <p className="mt-1 text-sm text-ink-soft">Your answers and progress in it go too. This cannot be undone.</p>
        {error && <p className="mt-2 text-sm font-semibold text-rose">{error}</p>}
        <div className="mt-5 flex justify-center gap-3">
          <button className="btn btn-ghost" autoFocus disabled={busy} onClick={onCancel}>
            Cancel
          </button>
          <button className="btn !border-[#c9453b] !bg-[#e0645c] !text-white !shadow-[0_3px_0_#a8362e]" disabled={busy} onClick={onDelete}>
            <Trash2 size={17} /> {busy ? 'Deleting…' : 'Delete'}
          </button>
        </div>
      </motion.div>
    </motion.div>,
    document.body,
  );
}

/**
 * A folder's name with a pencil and a bin beside it. The pencil turns the name into an input: Enter or the tick
 * saves, Escape or the cross puts the old name back. The bin asks first, then deletes the folder with everything in it.
 */
function FolderName({ name, parent, subfolder, className = '' }: { name: string; parent: string; subfolder?: string; className?: string }) {
  const setFolders = useStore((s) => s.setFolders);
  const refresh = useStore((s) => s.refresh);
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(name);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [deleting, setDeleting] = useState(false);

  const remove = async () => {
    setBusy(true);
    setError('');
    try {
      // the reply is the folders that are left: shown at once, no reload
      setFolders(await api.post<Tree>('/api/folders/delete', { parent, subfolder }));
      refresh().catch(() => {});
    } catch (e) {
      setError(messageOf(e));
      setBusy(false);
    }
  };

  const cancel = () => {
    setEditing(false);
    setValue(name);
    setError('');
  };
  const save = async () => {
    const next = value.trim();
    if (!next || next === name) return cancel();
    setBusy(true);
    setError('');
    try {
      // the reply is the folders as they now stand: shown at once, no reload
      setFolders(await api.post<Tree>('/api/folders/rename', { parent, subfolder, name: next }));
      setEditing(false);
      refresh().catch(() => {});
    } catch (e) {
      setError(messageOf(e));
    } finally {
      setBusy(false);
    }
  };

  if (!editing) {
    return (
      <span className="flex min-w-0 items-center gap-1.5">
        <span className={`truncate ${className}`}>{name}</span>
        <button
          onClick={() => {
            setValue(name);
            setEditing(true);
          }}
          aria-label={`Rename ${name}`}
          data-tip="Rename"
          className="shrink-0 cursor-pointer rounded-full p-1 text-ink-soft hover:bg-white/70 hover:text-ink"
        >
          <Pencil size={13} />
        </button>
        <button onClick={() => setDeleting(true)} aria-label={`Delete ${name}`} data-tip="Delete" className="shrink-0 cursor-pointer rounded-full p-1 text-ink-soft hover:bg-[#fbdcd8] hover:text-rose">
          <Trash2 size={13} />
        </button>
        {deleting && (
          <ConfirmDelete
            name={name}
            busy={busy}
            error={error}
            onCancel={() => {
              setDeleting(false);
              setError('');
            }}
            onDelete={remove}
          />
        )}
      </span>
    );
  }
  return (
    <form
      className="flex min-w-0 flex-wrap items-center gap-1.5"
      onSubmit={(e) => {
        e.preventDefault();
        save();
      }}
    >
      <input className="field !w-44 !py-1 font-bold" autoFocus value={value} maxLength={80} disabled={busy} onFocus={(e) => e.target.select()} onChange={(e) => setValue(e.target.value)} onKeyDown={(e) => e.key === 'Escape' && cancel()} aria-label={`New name for ${name}`} />
      <button type="submit" disabled={busy || !value.trim()} aria-label="Save the new name" data-tip="Save (Enter)" className="grid h-7 w-7 cursor-pointer place-items-center rounded-full bg-sage-soft text-sage-deep hover:bg-sage">
        <Check size={15} />
      </button>
      <button type="button" onClick={cancel} aria-label="Cancel renaming" data-tip="Cancel (Esc)" className="grid h-7 w-7 cursor-pointer place-items-center rounded-full bg-[#fbdcd8] text-rose hover:bg-[#f6c5bf]">
        <X size={15} />
      </button>
      {error && <span className="basis-full text-xs text-rose">{error}</span>}
    </form>
  );
}

/** One document inside a subfolder: its progress, its weak spots, and a way to practise only it. */
function DocumentRow({ doc }: { doc: FolderDoc }) {
  const refresh = useStore((s) => s.refresh);
  const parents = useStore((s) => s.folders.suggestions);
  const active = useStore((s) => s.activeDocument) === doc.id;
  const type = useStore((s) => s.questionType);
  const marks = useStore((s) => s.questionMarks[s.questionType]);
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState('');
  const [moving, setMoving] = useState(false);
  const [subject, setSubject] = useState(doc.subject_detected ? doc.subject : '');
  const [parent, setParent] = useState(doc.parent);

  const run = async (fn: () => Promise<unknown>, after?: () => void) => {
    setBusy(true);
    setNote('');
    try {
      await fn();
      await refresh();
      after?.();
    } catch (e) {
      setNote(messageOf(e));
    } finally {
      setBusy(false);
    }
  };
  // the questions are written from this one document only
  const write = () => run(() => api.post('/api/questions/generate', { study_material_id: doc.material_id, question_type: type, marks, number_of_questions: typeInfo(type).batch, difficulty: 'medium' }), () => navigate(`/session/${doc.id}`));
  const move = () => run(() => api.patch(`/api/study-materials/${doc.material_id}`, { subject, parent }), () => setMoving(false));

  const upload = doc.kind === 'upload';
  const unread = doc.processing_status !== 'PROCESSED';
  const Icon = upload ? FileText : BookOpen;

  return (
    <li className={`rounded-2xl border-[1.5px] bg-paper px-3 py-2.5 ${active ? 'border-lavender-deep' : 'border-line'} ${doc.answered ? '' : 'conf-neutral'}`} style={{ borderLeft: `6px solid ${tone(doc.confidence, doc.answered).accent}` }}>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <Icon size={20} className="shrink-0 text-oak-deep" />
        <div className="min-w-0 flex-1 basis-40">
          <div className="flex items-center gap-1.5">
            <span className="truncate font-bold">{doc.title}</span>
            {active && <span className="chip shrink-0 bg-lavender-soft !py-0.5 text-xs font-bold text-lavender-deep">Active</span>}
            {upload && (
              <button onClick={() => setMoving(!moving)} aria-label="Move to another folder" data-tip={doc.subject_detected ? 'Move to another folder' : "We couldn't detect the subtopic — set it here"} className="shrink-0 cursor-pointer text-ink-soft hover:text-ink">
                <Pencil size={13} />
              </button>
            )}
          </div>
          <div className="truncate text-xs text-ink-soft">
            {upload ? doc.file_name : 'Verified questions that come with HamSTAR'}
            {doc.question_count > 0 && ` · ${doc.answered} of ${doc.question_count} answered`}
            {doc.score != null && ` · ${doc.score}% correct`}
            {doc.vs_average != null && Math.abs(doc.vs_average) >= 5 && ` (${Math.abs(doc.vs_average)} ${doc.vs_average < 0 ? 'below' : 'above'} your average)`}
          </div>
        </div>
        <Confidence value={doc.confidence} answered={doc.answered} />
        {doc.question_count > 0 ? (
          <Link to={`/session/${doc.id}`} className="btn btn-primary !px-3 !py-1.5 text-sm">
            {doc.answered ? 'Continue' : 'Start learning'} <ArrowRight size={16} />
          </Link>
        ) : unread ? null : (
          <button className="btn btn-lilac !px-3 !py-1.5 text-sm" disabled={busy} onClick={write}>
            {busy ? 'Writing…' : 'Write the questions'} <ArrowRight size={16} />
          </button>
        )}
      </div>

      {unread && <p className="mt-1.5 text-sm text-ink-soft">I couldn't read this file. {doc.processing_error ?? ''}</p>}

      {doc.weak && (
        <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-2 rounded-xl bg-[#fdeedd] px-3 py-2" role="status">
          <TriangleAlert size={18} className="shrink-0 text-[#c9701a]" />
          <div className="min-w-0 flex-1 basis-48 text-sm">
            <b>You are weak in this document — want to improve?</b>
            {doc.weak_concepts.length > 0 && <span className="text-ink-soft"> Trickiest so far: {doc.weak_concepts.map((c) => c.concept).join(', ')}.</span>}
          </div>
          <Link to={practiceLink(doc.id)} className="btn btn-lilac !px-3 !py-1.5 text-sm">
            <Sparkles size={15} /> Practice This
          </Link>
        </div>
      )}

      {moving && (
        <form
          className="mt-2 flex flex-wrap items-end gap-2 rounded-xl bg-cream px-3 py-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (subject.trim()) move();
          }}
        >
          <label className="min-w-36 flex-1 text-xs font-bold">
            Parent folder
            <input className="field mt-0.5 !py-1 font-normal" list="parent-folders" value={parent} maxLength={80} onChange={(e) => setParent(e.target.value)} />
          </label>
          <label className="min-w-36 flex-1 text-xs font-bold">
            Subfolder
            <input className="field mt-0.5 !py-1 font-normal" list={`subfolders-${doc.id}`} autoFocus value={subject} maxLength={80} placeholder="e.g. Thermodynamics" onChange={(e) => setSubject(e.target.value)} />
          </label>
          <datalist id={`subfolders-${doc.id}`}>
            {(parents.find((p) => p.name.toLowerCase() === parent.trim().toLowerCase())?.subfolders ?? []).map((s) => (
              <option key={s} value={s} />
            ))}
          </datalist>
          <button className="btn btn-primary !px-3 !py-1" disabled={busy || !subject.trim()}>
            Move
          </button>
        </form>
      )}
      {note && <p className="mt-1.5 text-sm text-rose">{note}</p>}
    </li>
  );
}

function SubfolderRow({ parent, sub, open, toggle }: { parent: string; sub: Subfolder; open: boolean; toggle: () => void }) {
  return (
    <li className={`rounded-2xl bg-cream/80 ${tintClass(sub.answered)}`} style={tinted(sub.confidence, sub.answered)}>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2">
        <div className="flex min-w-0 flex-1 basis-40 items-center gap-2">
          <button className="flex shrink-0 cursor-pointer items-center gap-2" onClick={toggle} aria-expanded={open} aria-label={`${open ? 'Close' : 'Open'} ${sub.name}`}>
            <ChevronRight size={18} className={`text-ink-soft transition-transform duration-200 ${open ? 'rotate-90' : ''}`} />
            {open ? <FolderOpen size={20} className="text-oak-deep" /> : <Folder size={20} className="text-oak-deep" />}
          </button>
          <FolderName name={sub.name} parent={parent} subfolder={sub.name} className="font-extrabold" />
          <span className="shrink-0 text-xs text-ink-soft">
            {sub.document_count} document{sub.document_count === 1 ? '' : 's'}
          </span>
          {sub.weak && <TriangleAlert size={15} className="shrink-0 text-[#c9701a]" aria-label="Has a weak document" />}
        </div>
        <Confidence value={sub.confidence} answered={sub.answered} />
      </div>
      <Collapse open={open}>
        <ul className="space-y-2 px-3 pb-3">
          {sub.documents.map((d) => (
            <DocumentRow key={d.id} doc={d} />
          ))}
          <li>
            <Link to={`/upload?parent=${encodeURIComponent(parent)}&subject=${encodeURIComponent(sub.name)}`} className="inline-flex items-center gap-1 text-sm font-bold text-lavender-deep hover:underline">
              <Plus size={15} /> Add another document to {sub.name}
            </Link>
          </li>
        </ul>
      </Collapse>
    </li>
  );
}

/**
 * Parent folders → subfolders → documents. Each is coloured by its confidence score and can be renamed.
 * Weak documents come first; a parent folder names its weakest subfolder and offers to improve it.
 */
export function FolderTree({ onSelect }: { onSelect?: (parent: string | null) => void }) {
  const folders = useStore((s) => s.folders.folders);
  const parents = useStore((s) => s.folders.suggestions);
  const hidden = useStore((s) => s.folders.hidden_starters ?? 0);
  const setFolders = useStore((s) => s.setFolders);
  const restore = () => api.post<Tree>('/api/folders/restore-starters').then(setFolders).catch(() => {});
  // everything starts open; what the student closes stays closed while they are on the page
  const [closed, setClosed] = useState<Set<string>>(new Set());
  const flip = (key: string) =>
    setClosed((s) => {
      const next = new Set(s);
      if (!next.delete(key)) next.add(key);
      return next;
    });

  return (
    <div className="space-y-3">
      <Legend />
      {!folders.length && <p className="tile text-center text-ink-soft">No folders here yet. Upload some study material and I will make one for it.</p>}
      <datalist id="parent-folders">
        {[...new Set([...folders.map((f) => f.name), ...parents.map((p) => p.name)])].map((p) => (
          <option key={p} value={p} />
        ))}
      </datalist>
      {folders.map((f: ParentFolder) => {
        const open = !closed.has(f.name);
        const t = tone(f.confidence, f.answered);
        return (
          <section key={f.name} className={`tile !p-0 ${tintClass(f.answered)}`} style={tinted(f.confidence, f.answered)} onMouseEnter={() => onSelect?.(f.name)} onFocus={() => onSelect?.(f.name)}>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-2 p-3">
              <div className="flex min-w-0 flex-1 basis-48 items-center gap-3">
                <button className="flex shrink-0 cursor-pointer items-center gap-3" onClick={() => flip(f.name)} aria-expanded={open} aria-label={`${open ? 'Close' : 'Open'} ${f.name}`}>
                  <ChevronRight size={20} className={`text-ink-soft transition-transform duration-200 ${open ? 'rotate-90' : ''}`} />
                  <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-white/70" style={{ boxShadow: `inset 0 0 0 2px ${t.accent}` }}>
                    <FolderOpen size={24} className="text-oak-deep" />
                  </span>
                </button>
                <span className="min-w-0">
                  <FolderName name={f.name} parent={f.name} className="text-lg leading-tight font-extrabold" />
                  <span className="block text-xs text-ink-soft">
                    {f.subfolders.length} subfolder{f.subfolders.length === 1 ? '' : 's'} · {f.document_count} document{f.document_count === 1 ? '' : 's'} · {t.label}
                  </span>
                </span>
              </div>
              <Confidence value={f.confidence} answered={f.answered} />
            </div>
            {f.weakest && (
              <div className="mx-3 mb-3 flex flex-wrap items-center gap-x-3 gap-y-2 rounded-xl bg-white/70 px-3 py-2 text-sm">
                <span className="min-w-0 flex-1 basis-48">
                  You are weakest in: <b>{f.weakest.subfolder}</b> <span className="text-ink-soft">({f.weakest.confidence}/100)</span>
                </span>
                <Link to={practiceLink(f.weakest.document)} className="btn btn-primary !px-3 !py-1.5 text-sm">
                  Improve Now <ArrowRight size={16} />
                </Link>
              </div>
            )}
            <Collapse open={open}>
              <ul className="space-y-2 px-3 pb-3">
                {f.subfolders.map((s) => {
                  const key = `${f.name}/${s.name}`;
                  return <SubfolderRow key={key} parent={f.name} sub={s} open={!closed.has(key)} toggle={() => flip(key)} />;
                })}
              </ul>
            </Collapse>
          </section>
        );
      })}
      {hidden > 0 && (
        <button className="inline-flex cursor-pointer items-center gap-1.5 text-sm font-bold text-ink-soft hover:text-ink" onClick={restore}>
          <Undo2 size={15} /> Bring back the starter folder{hidden === 1 ? '' : 's'} I deleted ({hidden})
        </button>
      )}
    </div>
  );
}
