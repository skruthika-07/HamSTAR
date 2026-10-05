import { motion } from 'framer-motion';
import { ImagePlus, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

const MAX_MB = 8;

/** Keeps an object URL for a file alive exactly as long as the file is in use. */
export function useObjectUrl(file: File | null) {
  const [url, setUrl] = useState('');
  useEffect(() => {
    if (!file) return setUrl('');
    const u = URL.createObjectURL(file);
    setUrl(u);
    return () => URL.revokeObjectURL(u);
  }, [file]);
  return url;
}

/**
 * 📷 Upload Image: a photo of the working, a diagram or a solution, sent along with the typed answer.
 * The photo is kept with the answer for reference; nothing reads it.
 */
export function PhotoAttach({ file, onChange, disabled }: { file: File | null; onChange: (f: File | null) => void; disabled?: boolean }) {
  const input = useRef<HTMLInputElement>(null);
  const url = useObjectUrl(file);
  const [error, setError] = useState('');

  const choose = (f: File | undefined) => {
    setError('');
    if (!f) return;
    if (!/^image\/(png|jpe?g|webp)$/.test(f.type)) return setError('Pick a PNG, JPG or WebP photo.');
    if (f.size > MAX_MB * 1024 * 1024) return setError(`That photo is over ${MAX_MB} MB. Try a smaller one.`);
    onChange(f);
  };

  return (
    <div className="mt-2">
      <input
        ref={input}
        type="file"
        accept="image/png,image/jpeg,image/webp"
        className="hidden"
        onChange={(e) => {
          choose(e.target.files?.[0]);
          e.target.value = '';
        }}
      />
      <button type="button" className="btn btn-ghost !py-1.5 text-sm" onClick={() => input.current?.click()} disabled={disabled}>
        <ImagePlus size={16} /> {file ? 'Change image' : 'Upload Image'}
      </button>
      {error && <span className="ml-3 text-sm text-rose">{error}</span>}
      {file && url && (
        <motion.figure initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="relative mt-3 w-fit max-w-full rounded-2xl border-2 border-dashed border-line bg-cream p-2">
          <img src={url} alt="Your uploaded working" className="block max-h-64 max-w-full rounded-xl object-contain" />
          <figcaption className="mt-1 flex items-center justify-between gap-3 px-1 text-xs text-ink-soft">
            <span className="truncate">{file.name} · sent with your answer</span>
          </figcaption>
          <button type="button" aria-label="Remove image" disabled={disabled} onClick={() => onChange(null)} className="absolute -right-2 -top-2 grid h-7 w-7 place-items-center rounded-full bg-ink text-cream shadow">
            <X size={14} />
          </button>
        </motion.figure>
      )}
    </div>
  );
}

/** What the student sent, shown beside the result: their typed answer and, if they added one, their photo. */
export function YourAnswer({ text, photoUrl }: { text: string; photoUrl?: string }) {
  const [big, setBig] = useState(false);
  if (!text && !photoUrl) return null;
  return (
    <div className="flex w-full max-w-2xl flex-wrap items-start gap-3 rounded-2xl bg-cream px-4 py-3 text-left">
      <div className="min-w-0 flex-1 basis-48">
        <div className="eyebrow">Your answer</div>
        <p className="whitespace-pre-wrap text-[0.95rem]">{text || '—'}</p>
      </div>
      {photoUrl && (
        <button type="button" onClick={() => setBig(!big)} aria-label={big ? 'Shrink your photo' : 'Enlarge your photo'} className="shrink-0">
          <img src={photoUrl} alt="The working you sent" className={`rounded-xl border border-line object-contain transition-all ${big ? 'max-h-96 max-w-full' : 'max-h-28 max-w-40'}`} />
        </button>
      )}
    </div>
  );
}
