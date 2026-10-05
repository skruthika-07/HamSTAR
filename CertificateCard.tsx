import { AnimatePresence, motion } from 'framer-motion';
import { Copy, Crown, Lock, Printer, Share2, X } from 'lucide-react';
import { useState } from 'react';
import { TIARA_FOR_CERTIFICATE, useStore } from '../store/useStore';
import { HamstarMascot } from './mascot/HamstarMascot';
import { useScores } from './ScorePanel';

function Seal() {
  return (
    <svg viewBox="0 0 80 80" width="72" height="72" aria-hidden>
      <path d="M26,52 L18,78 L30,70 L36,80 L40,54 Z M54,52 L62,78 L50,70 L44,80 L40,54 Z" fill="#6B4FA0" />
      <circle cx="40" cy="36" r="27" fill="#27375A" stroke="#C9A227" strokeWidth="3" />
      <circle cx="40" cy="36" r="21" fill="none" stroke="#E3CE8A" strokeWidth="1.2" strokeDasharray="2 3" />
      <path d="M28,44 L26,28 L34,34 L40,24 L46,34 L54,28 L52,44 Z" fill="#F6C94D" />
    </svg>
  );
}

/** The certificate itself, laid out to be shown or printed. */
export function CertificateDocument() {
  const { profile, stats, certificate } = useStore();
  const { topics, total } = useScores();
  const date = new Date(certificate?.at ?? Date.now()).toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' });
  const facts = [
    ['Tiaras earned', String(stats.tiara)],
    ['Confidence score', `${total}/100`],
    ['Subjects mastered', String(topics.filter((t) => t.confidence > 70).length)],
    ['Best streak', String(stats.bestStreak)],
    ['Mistakes corrected', String(stats.mistakesCorrected)],
  ];
  return (
    <div className="relative mx-auto w-full bg-[#FFFBF2] p-3 text-center shadow-xl" style={{ border: '2px solid #C9A227', fontFamily: 'var(--font-sans)' }}>
      <div className="px-5 py-8 sm:px-12 sm:py-9" style={{ border: '1px solid #E3CE8A', backgroundImage: 'var(--grain)' }}>
        <div className="text-3xl font-bold text-[#27375A]" style={{ fontFamily: 'var(--font-serif)' }}>
          HamSTA<sup className="text-[0.55em] text-[#C9A227]">+</sup>R
        </div>
        <div className="mt-1 text-xs tracking-[0.3em] text-[#4a6a9a]">THINK · EXPLAIN · GROW</div>

        <h2 className="mt-5 text-2xl uppercase tracking-[0.1em] text-[#a8791a] sm:text-4xl" style={{ fontFamily: 'var(--font-serif)', fontWeight: 700 }}>
          Certificate <span className="text-[0.6em]">of</span> Achievement
        </h2>
        <div className="mx-auto mt-3 h-px w-56 bg-[#C9A227]" />

        <p className="mt-5 text-sm text-[#27375A]">This certificate is proudly presented to</p>
        <p className="mt-1 text-5xl text-[#27375A] sm:text-6xl" style={{ fontFamily: 'var(--font-script)' }}>
          {profile.name || 'Student'}
        </p>
        <div className="mx-auto mt-2 h-px w-72 max-w-full bg-[#C9A227]" />

        <p className="mx-auto mt-4 max-w-xl text-sm leading-relaxed text-[#27375A]">
          for earning {TIARA_FOR_CERTIFICATE} Tiara on HamSTA+R by answering questions correctly, explaining their reasoning, and correcting their own mistakes through evidence rather than guesswork.
        </p>

        <div className="mx-auto mt-5 grid max-w-2xl grid-cols-2 gap-px overflow-hidden rounded-xl border border-[#E3CE8A] bg-[#E3CE8A] sm:grid-cols-5">
          {facts.map(([label, value]) => (
            <div key={label} className="bg-[#FFFBF2] px-2 py-2.5">
              <div className="text-xl font-extrabold tabular-nums text-[#27375A]">{value}</div>
              <div className="text-[0.68rem] text-ink-soft">{label}</div>
            </div>
          ))}
        </div>

        <div className="mt-6 grid grid-cols-3 items-end gap-4 text-left text-xs">
          <div>
            <div className="text-2xl text-[#27375A]" style={{ fontFamily: 'var(--font-script)' }}>
              HamSTAR
            </div>
            <div className="border-t border-ink/40 pt-1 text-ink-soft">Learning companion</div>
          </div>
          <div className="flex justify-center">
            <Seal />
          </div>
          <div className="text-right">
            <div className="font-bold">{date}</div>
            <div className="border-t border-ink/40 pt-1 text-ink-soft">Issue date</div>
            <div className="mt-2 font-mono font-bold">{certificate?.id ?? 'PREVIEW'}</div>
            <div className="border-t border-ink/40 pt-1 text-ink-soft">Certificate ID</div>
          </div>
        </div>
      </div>
    </div>
  );
}

function LinkedInIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden>
      <rect width="24" height="24" rx="4" fill="#0A66C2" />
      <path d="M7.1 9.6v8H4.6v-8zM5.85 5.6a1.45 1.45 0 110 2.9 1.45 1.45 0 010-2.9zM9.3 9.6h2.4v1.1c.4-.7 1.3-1.3 2.6-1.3 2.6 0 3.1 1.7 3.1 3.9v4.3h-2.5v-3.8c0-.9 0-2.1-1.3-2.1s-1.5 1-1.5 2v3.9H9.3z" fill="#fff" />
    </svg>
  );
}

function WhatsAppIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden>
      <circle cx="12" cy="12" r="12" fill="#25D366" />
      <path d="M12 5.5a6.5 6.5 0 00-5.6 9.8L5.5 18.5l3.3-.9A6.5 6.5 0 1012 5.5z" fill="none" stroke="#fff" strokeWidth="1.5" strokeLinejoin="round" />
      <path d="M9.7 9.3c0 2.7 2.3 5 5 5" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

/** Opens each network's real share page. The link itself is a placeholder: there is no hosted certificate page. */
function ShareRow() {
  const { profile, certificate } = useStore();
  const [note, setNote] = useState('');
  const link = `${window.location.origin}/#/certificate/${certificate?.id ?? ''}`;
  const text = `${profile.name} earned the HamSTA+R Certificate of Achievement (${TIARA_FOR_CERTIFICATE} Tiara).`;
  const open = (url: string) => window.open(url, '_blank', 'noopener');
  const flash = (msg: string) => {
    setNote(msg);
    setTimeout(() => setNote(''), 3500);
  };
  return (
    <div className="no-print mt-3 rounded-2xl bg-paper p-3">
      <div className="flex flex-wrap items-center justify-center gap-2.5">
        <button className="btn btn-ghost" onClick={() => open(`https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(link)}`)}>
          <LinkedInIcon /> LinkedIn
        </button>
        <button className="btn btn-ghost" onClick={() => open(`https://wa.me/?text=${encodeURIComponent(`${text} ${link}`)}`)}>
          <WhatsAppIcon /> WhatsApp
        </button>
        <button
          className="btn btn-ghost"
          onClick={async () => {
            if (navigator.share) {
              try {
                await navigator.share({ title: 'HamSTA+R certificate', text, url: link });
              } catch {
                /* share sheet dismissed */
              }
            } else flash('This browser has no share sheet. Use Copy link instead.');
          }}
        >
          <Share2 size={16} /> Social media
        </button>
        <button
          className="btn btn-ghost"
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(link);
              flash('Link copied.');
            } catch {
              flash(link);
            }
          }}
        >
          <Copy size={16} /> Copy link
        </button>
        <button className="btn btn-ghost" onClick={() => window.print()}>
          <Printer size={16} /> Print
        </button>
      </div>
      <p className="mt-2 text-center text-xs text-ink-soft" aria-live="polite">
        {note || 'Demo: the share link is a placeholder, there is no hosted certificate page yet.'}
      </p>
    </div>
  );
}

export function CertificateModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-50 overflow-y-auto bg-ink/60 p-3 sm:p-6" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose} role="dialog" aria-modal="true" aria-label="Certificate">
          <motion.div initial={{ y: 30, scale: 0.96 }} animate={{ y: 0, scale: 1 }} exit={{ y: 30, opacity: 0 }} className="mx-auto max-w-3xl" onClick={(e) => e.stopPropagation()}>
            <div className="no-print mb-3 flex justify-end">
              <button className="btn btn-dark" onClick={onClose}>
                <X size={16} /> Close
              </button>
            </div>
            <CertificateDocument />
            <ShareRow />
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

/** Locked until 500 Tiara; then the hamster holds the certificate up and it can be opened and shared. */
export function CertificateCard() {
  const tiara = useStore((s) => s.stats.tiara);
  const certificate = useStore((s) => s.certificate);
  const [open, setOpen] = useState(false);
  const unlocked = !!certificate;
  const shown = Math.min(tiara, TIARA_FOR_CERTIFICATE);

  return (
    <section className="tile flex flex-wrap items-center gap-4">
      <HamstarMascot state={unlocked ? 'certificate' : 'thinking'} size={112} />
      <div className="min-w-[12rem] flex-1">
        <div className="eyebrow">Certificate of Achievement</div>
        <h2 className="text-lg leading-tight">{unlocked ? 'Unlocked!' : `Unlocks at ${TIARA_FOR_CERTIFICATE} Tiara`}</h2>
        <p className="text-sm text-ink-soft">{unlocked ? `Issued ${new Date(certificate.at).toLocaleDateString()} · ${certificate.id}` : 'Every correct question earns exactly one Tiara. Opening or attempting a question earns none.'}</p>
        <div className="mt-2 flex items-center gap-3">
          <div className="bar flex-1">
            <motion.span className="bg-gold" initial={{ width: 0 }} animate={{ width: `${(shown / TIARA_FOR_CERTIFICATE) * 100}%` }} transition={{ duration: 1 }} />
          </div>
          <span className="flex items-center gap-1 text-sm font-extrabold tabular-nums">
            <Crown size={15} className="text-gold-deep" /> {shown} / {TIARA_FOR_CERTIFICATE}
          </span>
        </div>
      </div>
      {unlocked ? (
        <button className="btn btn-primary shrink-0" onClick={() => setOpen(true)}>
          View and share
        </button>
      ) : (
        <span className="chip shrink-0 bg-cream-2 font-bold text-ink-soft">
          <Lock size={13} /> {TIARA_FOR_CERTIFICATE - shown} to go
        </span>
      )}
      <CertificateModal open={open} onClose={() => setOpen(false)} />
    </section>
  );
}
