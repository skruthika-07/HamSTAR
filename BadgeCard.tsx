import { motion } from 'framer-motion';
import { Flame, Footprints, Lock, SearchCheck } from 'lucide-react';
import { useStore, type BadgeId } from '../store/useStore';
import { HamstarMascot, type MascotVariant } from './mascot/HamstarMascot';

export const BADGES: Record<BadgeId, { name: string; about: string; requirement: string; variant: MascotVariant; bg: string; ring: string; shape: string }> = {
  streak: {
    name: 'Perfect Paw Streak',
    about: 'For a run of right answers without a single miss.',
    requirement: '10 correct answers in a row',
    variant: 'graduate',
    bg: 'linear-gradient(160deg,#FBEDC6,#F1C65B)',
    ring: '#9A6F0C',
    // hexagon
    shape: 'polygon(50% 0%, 95% 25%, 95% 75%, 50% 100%, 5% 75%, 5% 25%)',
  },
  noskip: {
    name: 'No-Skip Scholar',
    about: 'For facing every question, even the scary ones.',
    requirement: '25 questions in a row without skipping',
    variant: 'reader',
    bg: 'linear-gradient(160deg,#EAF0DD,#A9C283)',
    ring: '#56733A',
    // circle
    shape: 'circle(50% at 50% 50%)',
  },
  mistakes: {
    name: 'Mistake Master',
    about: 'For going back to what went wrong and putting it right.',
    requirement: '50 mistakes corrected (understanding above 70%)',
    variant: 'cool',
    bg: 'linear-gradient(160deg,#F3ECFB,#B99BE0)',
    ring: '#6B4FA0',
    // shield
    shape: 'polygon(50% 0%, 96% 12%, 96% 58%, 50% 100%, 4% 58%, 4% 12%)',
  },
};

/** Each badge has its own shape, colour, hamster and motif. */
export function BadgeArt({ id, size = 96, unlocked }: { id: BadgeId; size?: number; unlocked: boolean }) {
  const b = BADGES[id];
  return (
    <motion.div
      className="relative shrink-0"
      data-tip={`${b.name}: ${b.requirement}`}
      style={{ width: size, height: size, filter: unlocked ? `drop-shadow(0 0 10px ${b.ring}66)` : 'grayscale(0.85) opacity(0.6)' }}
      animate={unlocked ? { rotate: [0, -3, 3, 0] } : {}}
      transition={{ duration: 3, repeat: Infinity, repeatDelay: 2 }}
    >
      <div className="absolute inset-0" style={{ clipPath: b.shape, background: b.ring }} />
      <div className="absolute inset-[5%] flex items-center justify-center overflow-hidden" style={{ clipPath: b.shape, background: b.bg }}>
        <HamstarMascot variant={b.variant} bust size={size * 0.78} title={b.name} />
      </div>

      {/* Motif unique to each badge */}
      {id === 'streak' && (
        <span className="absolute -right-1 -top-1 flex h-[34%] w-[34%] items-center justify-center rounded-full bg-ink text-gold shadow">
          <Flame size={size * 0.2} fill="currentColor" />
        </span>
      )}
      {id === 'noskip' && (
        <span className="absolute -bottom-1 left-1/2 flex -translate-x-1/2 items-center gap-0.5 rounded-full bg-ink px-2 py-0.5 text-sage">
          {[0, 1, 2].map((i) => (
            <motion.span key={i} animate={unlocked ? { opacity: [0.3, 1, 0.3] } : {}} transition={{ duration: 1.2, repeat: Infinity, delay: i * 0.25 }}>
              <Footprints size={size * 0.13} />
            </motion.span>
          ))}
        </span>
      )}
      {id === 'mistakes' && (
        <span className="absolute -bottom-1 -right-1 flex h-[36%] w-[36%] items-center justify-center rounded-xl bg-ink text-lavender shadow">
          <SearchCheck size={size * 0.2} />
        </span>
      )}
      {unlocked && (
        <motion.span className="absolute left-1 top-0 text-gold" animate={{ scale: [0, 1, 0], rotate: [0, 90] }} transition={{ duration: 1.6, repeat: Infinity, repeatDelay: 1 }}>
          ✦
        </motion.span>
      )}
      {!unlocked && (
        <span className="absolute left-0 top-0 flex h-7 w-7 items-center justify-center rounded-full bg-ink text-cream">
          <Lock size={13} />
        </span>
      )}
    </motion.div>
  );
}

export function BadgeCard({ id, compact = false }: { id: BadgeId; compact?: boolean }) {
  // progress and unlocking are decided by the server
  const badge = useStore((s) => s.badges.find((x) => x.id === id));
  const progress = badge?.progress ?? 0;
  const target = badge?.target ?? 1;
  // the demo preview shows the badge as it looks once earned; it awards nothing
  const preview = useStore((s) => s.badgePreview);
  const earned = !!badge?.unlocked;
  const unlocked = preview || earned;
  const b = BADGES[id];
  const shown = earned ? target : progress;

  return (
    <div className={`card flex items-center gap-4 p-4 ${compact ? 'xl:flex-col xl:text-center' : ''} ${unlocked ? '' : 'bg-cream'}`}>
      <BadgeArt id={id} size={compact ? 68 : 88} unlocked={unlocked} />
      <div className="w-full min-w-0 flex-1">
        <div className={`flex flex-wrap items-center gap-2 ${compact ? 'xl:justify-center' : ''}`}>
          <h3 className="text-base font-semibold">{b.name}</h3>
          <span className={`chip ${unlocked ? 'bg-sage-soft text-sage-deep' : 'bg-cream-2 text-ink-soft'}`}>{preview && !earned ? 'Demo preview' : unlocked ? 'Unlocked' : 'Locked'}</span>
        </div>
        <p className="mt-0.5 text-sm">{b.about}</p>
        <p className="mt-0.5 text-sm text-ink-soft">
          <b>To unlock:</b> {b.requirement}
        </p>
        <div className="mt-2.5 flex items-center gap-3">
          <div className="h-2 flex-1 rounded-full bg-cream-2">
            <motion.div className="h-2 rounded-full" style={{ background: b.ring }} initial={{ width: 0 }} animate={{ width: `${((preview ? target : shown) / target) * 100}%` }} transition={{ duration: 0.8 }} />
          </div>
          <span className="text-sm font-semibold tabular-nums">
            {shown} / {target}
            {preview && !earned && <span className="font-normal text-ink-soft"> (real)</span>}
          </span>
        </div>
      </div>
    </div>
  );
}
