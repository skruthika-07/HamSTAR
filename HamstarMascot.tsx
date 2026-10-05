import { motion } from 'framer-motion';
import { useEffect, useId, useState, type ReactNode } from 'react';
import { useStore, type AvatarId } from '../../store/useStore';

export type MascotState =
  | 'idle'
  | 'reading'
  | 'thinking'
  | 'listening'
  | 'analyzing'
  | 'confident'
  | 'spinning'
  | 'correct'
  | 'wrong'
  | 'investigating'
  | 'explaining'
  | 'question'
  | 'uploading'
  | 'processing'
  | 'celebrating'
  | 'encouraging'
  | 'reward'
  | 'badge'
  | 'certificate'
  | 'profile'
  | 'customizing'
  | 'welcome'
  | 'password'
  | 'settings'
  | 'attitude';

export type MascotVariant = AvatarId;

type Arm = number | number[];
type Prop = 'book' | 'bookUp' | 'magnifier' | 'notebook' | 'card' | 'doc' | 'certificate' | 'wheel' | 'gear' | 'badge' | 'pointer';
type Fx = 'sparkles' | 'waves' | 'confetti' | 'dots' | 'crown' | 'page' | 'scan';

interface Pose {
  body: 'breathe' | 'hop' | 'bounce' | 'walk' | 'run' | 'flinch';
  head: 'still' | 'nod' | 'tilt' | 'scan';
  eyes: 'open' | 'read' | 'side' | 'up' | 'closed' | 'happy';
  mouth: 'neutral' | 'smile' | 'o' | 'talk';
  brows?: 'worried' | 'raised';
  /** Arm angles in degrees from hanging straight down. Arrays animate back and forth. */
  L: Arm;
  R: Arm;
  armDur?: number;
  prop?: Prop;
  bulb?: 'dim' | 'on' | 'pop';
  fx?: Fx[];
}

const POSES: Record<string, Pose> = {
  // Never truly idle: looks around and gives a small wave now and then.
  idle: { body: 'breathe', head: 'tilt', eyes: 'side', mouth: 'smile', L: [-24, -18], R: [20, 30], armDur: 1.8 },
  reading: { body: 'breathe', head: 'still', eyes: 'read', mouth: 'smile', L: [8, 12], R: [-8, -12], armDur: 1.8, prop: 'book', fx: ['page'] },
  thinking: { body: 'breathe', head: 'tilt', eyes: 'up', mouth: 'neutral', L: -18, R: [150, 160], armDur: 0.7, bulb: 'dim', fx: ['dots'] },
  listening: { body: 'breathe', head: 'nod', eyes: 'open', mouth: 'neutral', L: -32, R: [36, 50], armDur: 0.3, prop: 'notebook', fx: ['waves'] },
  analyzing: { body: 'breathe', head: 'scan', eyes: 'side', mouth: 'neutral', L: -18, R: [-72, -46], armDur: 0.9, prop: 'magnifier' },
  confident: { body: 'bounce', head: 'still', eyes: 'happy', mouth: 'smile', brows: 'raised', L: 34, R: -34 },
  // Runs inside the wheel; the bulb is still dark.
  spinning: { body: 'run', head: 'still', eyes: 'open', mouth: 'smile', L: [50, -50], R: [-50, 50], armDur: 0.16, prop: 'wheel', bulb: 'dim' },
  correct: { body: 'run', head: 'still', eyes: 'happy', mouth: 'smile', L: [50, -50], R: [-50, 50], armDur: 0.16, prop: 'wheel', bulb: 'on', fx: ['sparkles'] },
  wrong: { body: 'flinch', head: 'tilt', eyes: 'open', mouth: 'o', brows: 'worried', L: -150, R: 150, bulb: 'pop' },
  correctRun: { body: 'run', head: 'still', eyes: 'happy', mouth: 'smile', L: [50, -50], R: [-50, 50], armDur: 0.16, prop: 'wheel', bulb: 'on', fx: ['sparkles'] },
  correctCheer: { body: 'hop', head: 'still', eyes: 'happy', mouth: 'smile', L: [130, 155], R: [-130, -155], armDur: 0.3, prop: 'wheel', bulb: 'on', fx: ['sparkles', 'confetti'] },
  investigating: { body: 'breathe', head: 'scan', eyes: 'side', mouth: 'neutral', brows: 'raised', L: -18, R: [-78, -40], armDur: 1.1, prop: 'magnifier' },
  explaining: { body: 'breathe', head: 'nod', eyes: 'open', mouth: 'talk', L: -20, R: [-98, -76], armDur: 0.9, prop: 'pointer' },
  question: { body: 'breathe', head: 'tilt', eyes: 'open', mouth: 'smile', brows: 'raised', L: 4, R: -4, prop: 'card' },
  uploading: { body: 'walk', head: 'still', eyes: 'open', mouth: 'smile', L: 2, R: -2, prop: 'doc' },
  celebrating: { body: 'hop', head: 'still', eyes: 'happy', mouth: 'smile', L: [128, 152], R: [-128, -152], armDur: 0.35, fx: ['confetti'] },
  encouraging: { body: 'bounce', head: 'nod', eyes: 'happy', mouth: 'smile', L: 30, R: [-150, -128], armDur: 0.45 },
  reward: { body: 'bounce', head: 'still', eyes: 'happy', mouth: 'smile', L: 138, R: -138, fx: ['crown', 'sparkles'] },
  badge: { body: 'hop', head: 'still', eyes: 'happy', mouth: 'smile', L: 30, R: -140, prop: 'badge', fx: ['sparkles'] },
  certificate: { body: 'breathe', head: 'tilt', eyes: 'happy', mouth: 'smile', L: 16, R: -16, prop: 'certificate', fx: ['sparkles'] },
  profile: { body: 'breathe', head: 'tilt', eyes: 'open', mouth: 'smile', brows: 'raised', L: 20, R: [-150, -120], armDur: 0.5 },
  customizing: { body: 'bounce', head: 'tilt', eyes: 'happy', mouth: 'smile', L: [-66, -84], R: [66, 84], armDur: 0.4, fx: ['sparkles'] },
  // Privacy pose: eyes shut, book lifted over them.
  password: { body: 'breathe', head: 'still', eyes: 'closed', mouth: 'neutral', L: -168, R: 168, prop: 'bookUp' },
  settings: { body: 'breathe', head: 'scan', eyes: 'side', mouth: 'neutral', L: [48, 72], R: [36, 50], armDur: 0.5, prop: 'gear' },
  // In the logo: one paw on the hip, the other resting on the H beside it. Owns the place.
  attitude: { body: 'breathe', head: 'nod', eyes: 'happy', mouth: 'smile', brows: 'raised', L: 30, R: -66 },
  // Sub-poses used by cycling states.
  welcomeWave: { body: 'hop', head: 'still', eyes: 'happy', mouth: 'smile', L: -18, R: [-156, -124], armDur: 0.3 },
  welcomeBook: { body: 'breathe', head: 'nod', eyes: 'read', mouth: 'smile', L: 10, R: -10, prop: 'book', fx: ['page'] },
  welcomePoint: { body: 'breathe', head: 'still', eyes: 'side', mouth: 'smile', brows: 'raised', L: -18, R: [-96, -84], armDur: 0.4, prop: 'pointer' },
  procRead: { body: 'breathe', head: 'scan', eyes: 'read', mouth: 'neutral', L: 2, R: -2, prop: 'doc', fx: ['scan'] },
  procNotes: { body: 'breathe', head: 'nod', eyes: 'read', mouth: 'neutral', L: -32, R: [36, 50], armDur: 0.25, prop: 'notebook' },
};

/** States that play a short loop of sub-poses instead of a single pose. */
const CYCLES: Partial<Record<MascotState, string[]>> = {
  welcome: ['welcomeWave', 'welcomeBook', 'welcomePoint'],
  correct: ['correctRun', 'correctCheer'],
  processing: ['procRead', 'procNotes', 'analyzing', 'thinking'],
};

// Drawn after the reference hamster: one pear-shaped body, warm orange coat, cream muzzle and belly,
// dusty-pink ears, pink paws and feet, whiskers, a tuft on top.
const PEAR = 'M110,44 C150,44 165,70 164,96 C176,120 178,152 173,174 C168,198 146,206 110,206 C74,206 52,198 47,174 C42,152 44,120 56,96 C55,70 70,44 110,44 Z';
const PAW = '#F4B4A6';
const FUR = '#F3B26A';
const FUR_DARK = '#E39A4C';
const CREAM = '#FFF7EA';
const LINE = '#5B3A26';
const INK = '#2E2018';
const PINK = '#F6A8A6';
const GOLD = '#F6C94D';

interface Look {
  hat?: 'grad' | 'crown';
  glasses?: 'round' | 'shades';
  headphones?: boolean;
  sleepy?: boolean;
  backpack?: boolean;
  laptop?: boolean;
  bg: string;
}

/** The eight hamsters of "Choose your STAR". */
const LOOKS: Record<MascotVariant, Look> = {
  graduate: { hat: 'grad', bg: '#CDBBF0' },
  reader: { glasses: 'round', bg: '#FBD77A' },
  cool: { glasses: 'shades', bg: '#F7B4C5' },
  royal: { hat: 'crown', bg: '#B4D4F4' },
  music: { headphones: true, bg: '#AEDCAE' },
  sleepy: { sleepy: true, bg: '#C9BAF0' },
  explorer: { backpack: true, bg: '#F8C57A' },
  coder: { laptop: true, bg: '#94D2D8' },
};

export const VARIANT_INFO: Record<MascotVariant, { name: string; blurb: string; bg: string }> = {
  graduate: { name: 'Graduate', blurb: 'Cap on, ready to teach', bg: LOOKS.graduate.bg },
  reader: { name: 'Reader', blurb: 'Round glasses and a good book', bg: LOOKS.reader.bg },
  cool: { name: 'Cool', blurb: 'Shades on, calm under pressure', bg: LOOKS.cool.bg },
  royal: { name: 'Royal', blurb: 'Wears the Tiara', bg: LOOKS.royal.bg },
  music: { name: 'Music', blurb: 'Studies with headphones', bg: LOOKS.music.bg },
  sleepy: { name: 'Sleepy', blurb: 'Late-night reviser', bg: LOOKS.sleepy.bg },
  explorer: { name: 'Explorer', blurb: 'Backpack packed', bg: LOOKS.explorer.bg },
  coder: { name: 'Coder', blurb: 'Laptop always open', bg: LOOKS.coder.bg },
};

/**
 * Rotates/moves its children around the point (x, y). The invisible square
 * keeps the group's bounding box centred on that point, which is what the
 * transform origin of an animated SVG group is measured from.
 */
function Pivot({ x, y, animate, transition, children }: { x: number; y: number; animate: any; transition?: any; children: ReactNode }) {
  return (
    <g transform={`translate(${x} ${y})`}>
      <motion.g animate={animate} transition={transition}>
        <rect x={-150} y={-150} width={300} height={300} fill="none" pointerEvents="none" />
        {children}
      </motion.g>
    </g>
  );
}

const loop = (duration: number, extra: object = {}) => ({ duration, repeat: Infinity, repeatType: 'mirror' as const, ease: 'easeInOut' as const, ...extra });
const spring = { type: 'spring' as const, stiffness: 140, damping: 14 };

function ArmGroup({ x, y, angle, dur, children }: { x: number; y: number; angle: Arm; dur: number; children?: ReactNode }) {
  const keyed = Array.isArray(angle);
  return (
    <Pivot x={x} y={y} animate={{ rotate: angle }} transition={keyed ? loop(dur) : spring}>
      {children}
      {/* a short, plump forearm that widens into the shoulder, ending in a small mitten paw with toes */}
      <path d="M-9.5,-4 C-11.5,7 -10,16 -7.5,21.5 L7.5,21.5 C10,16 11.5,7 9.5,-4 Z" fill={FUR} stroke={LINE} strokeWidth={2.4} strokeLinejoin="round" />
      <path d="M-8,20.5 C-10,26.5 -5.5,33 0,33 C5.5,33 10,26.5 8,20.5 C5,18.5 -5,18.5 -8,20.5 Z" fill={PAW} stroke={LINE} strokeWidth={2.2} strokeLinejoin="round" />
      <path d="M-2.8,32.4 v-3.4 M2.8,32.4 v-3.4" stroke={LINE} strokeWidth={1.3} strokeLinecap="round" />
      {/* no outline where the arm grows out of the body */}
      <ellipse cx={0} cy={-3} rx={9.2} ry={7} fill={FUR} />
    </Pivot>
  );
}

const EYE_Y = 91;

function Eye({ cx, mode }: { cx: number; mode: Pose['eyes'] }) {
  if (mode === 'closed') return <path d={`M${cx - 6},${EYE_Y} q6,5 12,0`} stroke={INK} strokeWidth={2.6} fill="none" strokeLinecap="round" />;
  if (mode === 'happy') return <path d={`M${cx - 6},${EYE_Y + 2} q6,-8 12,0`} stroke={INK} strokeWidth={2.8} fill="none" strokeLinecap="round" />;
  const gaze =
    mode === 'read'
      ? { animate: { x: [-2, 2], y: 3 }, transition: { x: loop(1.5), y: { duration: 0.2 } } }
      : mode === 'side'
        ? { animate: { x: [-2.6, 2.6], y: 0 }, transition: { x: loop(1.7), y: { duration: 0.2 } } }
        : mode === 'up'
          ? { animate: { x: 1.5, y: -2.6 }, transition: { duration: 0.3 } }
          : { animate: { x: 0, y: 0 }, transition: { duration: 0.3 } };
  return (
    // blink
    <motion.g animate={{ scaleY: [1, 1, 0.1, 1] }} transition={{ duration: 3.4, times: [0, 0.92, 0.96, 1], repeat: Infinity }}>
      <motion.g {...gaze}>
        <circle cx={cx} cy={EYE_Y} r={6.6} fill={INK} />
        <circle cx={cx + 1.6} cy={EYE_Y - 2.2} r={2.2} fill="#fff" />
      </motion.g>
    </motion.g>
  );
}

function Bulb({ mode, x = 190, y = 36 }: { mode: NonNullable<Pose['bulb']>; x?: number; y?: number }) {
  const shards = [0, 45, 90, 135, 180, 225, 270, 315];
  return (
    <g transform={`translate(${x} ${y}) scale(1.25)`}>
      {mode === 'on' && (
        <>
          <motion.circle r={30} fill="#FFE9A0" initial={{ opacity: 0, scale: 0.4 }} animate={{ opacity: [0.25, 0.6, 0.25], scale: [1, 1.25, 1] }} transition={loop(0.9)} />
          <motion.circle r={20} fill={GOLD} initial={{ opacity: 0, scale: 0.4 }} animate={{ opacity: [0.35, 0.7, 0.35], scale: [1, 1.15, 1] }} transition={loop(0.7)} />
          {[0, 45, 90, 135, 180, 225, 270, 315].map((a) => (
            <motion.line key={a} x1={0} y1={-20} x2={0} y2={-26} stroke={GOLD} strokeWidth={2.4} strokeLinecap="round" transform={`rotate(${a})`} animate={{ opacity: [0.3, 1, 0.3] }} transition={loop(0.6, { delay: a / 900 })} />
          ))}
        </>
      )}
      {mode === 'pop' ? (
        <>
          {/* flicker, crack, then burst */}
          <motion.g initial={{ scale: 1, opacity: 1 }} animate={{ scale: [1, 1, 1.05, 1.4, 0.2], opacity: [1, 0.5, 1, 1, 0], x: [0, -1.5, 1.5, 0, 0] }} transition={{ duration: 0.75, times: [0, 0.2, 0.45, 0.8, 1] }}>
            <circle r={12} fill="#F4D98A" stroke={LINE} strokeWidth={1.8} />
            <motion.path d="M-2,-11 L2,-4 L-3,0 L3,5 L-1,11" stroke={LINE} strokeWidth={1.4} fill="none" strokeLinejoin="round" initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.4, delay: 0.1 }} />
          </motion.g>
          <motion.circle r={8} fill="none" stroke="#D9CBB5" strokeWidth={2} initial={{ scale: 0.4, opacity: 0 }} animate={{ scale: [0.4, 2.4], opacity: [0, 0.8, 0] }} transition={{ duration: 0.7, delay: 0.55 }} />
          {shards.map((a) => (
            <motion.path key={a} d="M0,-3 L2.5,2 L-2.5,2 Z" fill="#F4D98A" stroke={LINE} strokeWidth={0.6} initial={{ x: 0, y: 0, opacity: 0, rotate: a }} animate={{ x: Math.cos((a * Math.PI) / 180) * 24, y: Math.sin((a * Math.PI) / 180) * 24 + 6, opacity: [0, 1, 0], rotate: a + 160 }} transition={{ duration: 0.75, delay: 0.55, ease: 'easeOut' }} />
          ))}
          <motion.g initial={{ opacity: 0 }} animate={{ opacity: 1, rotate: [-4, 4] }} transition={{ opacity: { delay: 1 }, rotate: loop(1.4) }}>
            <path d="M-9,-2 L-5,-8 L-1,-3 L3,-9 L8,-3 L6,4 L-6,4 Z" fill="#EFE7DA" stroke="#9A8F83" strokeWidth={1.3} strokeLinejoin="round" />
            <rect x={-5} y={5} width={10} height={7} rx={2} fill="#8D8378" />
          </motion.g>
        </>
      ) : (
        <motion.g animate={mode === 'dim' ? { opacity: [0.45, 0.9, 0.45] } : { opacity: 1, scale: [1, 1.06, 1] }} transition={loop(mode === 'dim' ? 1.1 : 0.7)}>
          <circle r={12} fill={mode === 'on' ? '#FFD95E' : '#EFE7DA'} stroke={LINE} strokeWidth={1.8} />
          <path d="M-4,1 q2,-5 4,0 q2,-5 4,0" stroke={mode === 'on' ? '#9A6F0C' : '#9A8F83'} strokeWidth={1.3} fill="none" />
          <rect x={-5} y={11} width={10} height={7} rx={2} fill="#8D8378" />
        </motion.g>
      )}
    </g>
  );
}

const STAR = 'M0,-7 L1.7,-1.7 L7,0 L1.7,1.7 L0,7 L-1.7,1.7 L-7,0 L-1.7,-1.7 Z';
const CROWN = 'M92,48 L88,26 L100,36 L110,20 L120,36 L132,26 L128,48 Z';

function Crown() {
  return (
    <>
      <path d={CROWN} fill={GOLD} stroke={LINE} strokeWidth={2} strokeLinejoin="round" />
      <circle cx={110} cy={39} r={2.6} fill="#E8739A" />
      <circle cx={99} cy={41} r={1.8} fill="#8FC0EE" />
      <circle cx={121} cy={41} r={1.8} fill="#8FC0EE" />
    </>
  );
}

function Effects({ fx }: { fx: Fx[] }) {
  return (
    <>
      {fx.includes('sparkles') &&
        [
          [26, 62, 0],
          [196, 98, 0.3],
          [42, 20, 0.6],
          [168, 12, 0.9],
        ].map(([x, y, d], i) => (
          <g key={i} transform={`translate(${x} ${y})`}>
            <motion.path d={STAR} fill={GOLD} animate={{ scale: [0, 1, 0], rotate: [0, 45] }} transition={{ duration: 1.3, repeat: Infinity, delay: d }} />
          </g>
        ))}
      {fx.includes('waves') &&
        [0, 1, 2].map((i) => (
          <motion.path key={i} d={`M${40 - i * 9},${44 - i * 5} q-9,${12 + i * 4} 0,${24 + i * 8}`} stroke="#8a66c9" strokeWidth={2.4} fill="none" strokeLinecap="round" animate={{ opacity: [0.1, 1, 0.1] }} transition={{ duration: 1, repeat: Infinity, delay: (2 - i) * 0.18 }} />
        ))}
      {fx.includes('dots') &&
        [
          [164, 60, 2.6],
          [171, 52, 3.3],
          [178, 45, 4],
        ].map(([x, y, r], i) => <motion.circle key={i} cx={x} cy={y} r={r} fill="#B9AC9C" animate={{ opacity: [0.15, 1, 0.15] }} transition={{ duration: 1.2, repeat: Infinity, delay: i * 0.22 }} />)}
      {fx.includes('confetti') &&
        Array.from({ length: 6 }).map((_, i) => {
          const color = [GOLD, '#B99BE0', '#9DB877', '#E9A28B'][i % 4];
          return <motion.rect key={i} x={24 + i * 34} y={-6} width={5} height={9} rx={1.5} fill={color} animate={{ y: [0, 150], rotate: [0, 260], opacity: [1, 1, 0] }} transition={{ duration: 1.6 + (i % 3) * 0.3, repeat: Infinity, delay: (i % 5) * 0.2, ease: 'easeIn' }} />;
        })}
    </>
  );
}

interface Props {
  state?: MascotState;
  size?: number;
  /** Defaults to the hamster the student picked on their profile. */
  variant?: MascotVariant;
  /** Head-and-shoulders crop: profile pictures, badges, the hamster peeking over a card. */
  bust?: boolean;
  className?: string;
  title?: string;
}

export function HamstarMascot({ state = 'idle', size = 150, variant, bust = false, className, title }: Props) {
  const chosen = useStore((s) => s.profile.avatar);
  const look = LOOKS[variant ?? chosen] ?? LOOKS.reader;
  const clip = useId();

  const cycle = CYCLES[state];
  const [step, setStep] = useState(0);
  useEffect(() => {
    setStep(0);
    if (!cycle) return;
    const t = setInterval(() => setStep((s) => s + 1), 2400);
    return () => clearInterval(t);
  }, [state]); // eslint-disable-line react-hooks/exhaustive-deps
  const key = cycle ? cycle[step % cycle.length] : state;
  const p = POSES[key] ?? POSES.idle;

  const fx = bust ? [] : (p.fx ?? []);
  const prop = bust ? undefined : p.prop;
  const dur = p.armDur ?? 1.4;
  const eyes = look.sleepy && (p.eyes === 'open' || p.eyes === 'side') ? 'closed' : p.eyes;
  const hidden = look.glasses === 'shades' && p.eyes !== 'closed';

  const body =
    p.body === 'hop'
      ? { animate: { y: [0, -18, 0, -7, 0], rotate: 0, x: 0 }, transition: { duration: 0.95, repeat: Infinity, repeatDelay: 0.5 } }
      : p.body === 'bounce'
        ? { animate: { y: [0, -7, 0], rotate: 0, x: 0 }, transition: { duration: 0.6, repeat: Infinity, ease: 'easeInOut' as const } }
        : p.body === 'run'
          ? { animate: { y: [0, -5, 0], rotate: 7, x: 0 }, transition: { y: { duration: 0.2, repeat: Infinity }, rotate: { duration: 0.3 } } }
          : p.body === 'flinch'
            ? { animate: { y: [0, -12, 0, 0], rotate: [0, -7, -4, -3], x: [0, -6, -4, -4] }, transition: { duration: 0.6, times: [0, 0.3, 0.7, 1] } }
            : p.body === 'walk'
          ? { animate: { y: [0, -3, 0], rotate: [-3, 3], x: [-7, 7] }, transition: { y: { duration: 0.35, repeat: Infinity }, rotate: loop(0.35), x: loop(1.6) } }
          : { animate: { y: [0, -2, 0], rotate: 0, x: 0 }, transition: { duration: 2.6, repeat: Infinity, ease: 'easeInOut' as const } };

  const running = p.body === 'run';
  const inWheel = prop === 'wheel';
  const head =
    p.head === 'nod'
      ? { animate: { y: [0, 3, 0], rotate: 0 }, transition: { duration: 0.9, repeat: Infinity, ease: 'easeInOut' as const } }
      : p.head === 'tilt'
        ? { animate: { y: 0, rotate: [-4, 4] }, transition: loop(2.4) }
        : p.head === 'scan'
          ? { animate: { y: 0, rotate: [-3, 3] }, transition: loop(1.1) }
          : { animate: { y: 0, rotate: 0 }, transition: { duration: 0.3 } };

  return (
    <svg
      viewBox={bust ? '38 12 144 144' : '0 0 220 220'}
      width={size}
      height={size}
      className={className}
      role="img"
      aria-label={title ?? `HamSTAR hamster, ${state}`}
      style={{ overflow: bust ? 'hidden' : 'visible', flexShrink: 0 }}
    >
      <defs>
        <clipPath id={clip}>
          <path d={PEAR} />
        </clipPath>
      </defs>

      {!bust && !inWheel && <ellipse cx={110} cy={211} rx={56} ry={6} fill="rgba(70,40,15,0.13)" />}

      {inWheel && (
        // the hamster runs inside it
        <g>
          <path d="M70,214 L110,110 L150,214" fill="none" stroke="#B58A5A" strokeWidth={7} strokeLinecap="round" strokeLinejoin="round" />
          <path d="M56,216 H164" stroke={LINE} strokeWidth={5} strokeLinecap="round" />
          <Pivot x={110} y={110} animate={{ rotate: -360 }} transition={{ duration: 0.9, repeat: Infinity, ease: 'linear' }}>
            <circle r={98} fill="rgba(255,247,234,0.55)" stroke="#D9A66B" strokeWidth={9} />
            <circle r={103} fill="none" stroke={LINE} strokeWidth={2} />
            <circle r={93} fill="none" stroke={LINE} strokeWidth={1.4} />
            {Array.from({ length: 18 }).map((_, i) => (
              <line key={i} x1={0} y1={-93} x2={0} y2={-103} stroke={LINE} strokeWidth={2} transform={`rotate(${i * 20})`} />
            ))}
            {[0, 60, 120].map((a) => (
              <line key={a} x1={-92} y1={0} x2={92} y2={0} stroke="#E8CFA4" strokeWidth={3} transform={`rotate(${a})`} />
            ))}
          </Pivot>
          <circle cx={110} cy={110} r={7} fill="#B58A5A" stroke={LINE} strokeWidth={2} />
        </g>
      )}
      {prop === 'gear' && (
        <Pivot x={34} y={172} animate={{ rotate: 360 }} transition={{ duration: 3.2, repeat: Infinity, ease: 'linear' }}>
          {[0, 45, 90, 135, 180, 225, 270, 315].map((a) => (
            <rect key={a} x={-5} y={-29} width={10} height={12} rx={2} fill="#A79C90" stroke={LINE} strokeWidth={1.2} transform={`rotate(${a})`} />
          ))}
          <circle r={20} fill="#BFB4A6" stroke={LINE} strokeWidth={1.8} />
          <circle r={7} fill={CREAM} stroke={LINE} strokeWidth={1.8} />
        </Pivot>
      )}

      <g transform={inWheel ? 'translate(110 200) scale(0.74) translate(-110 -206)' : undefined}>
      <motion.g {...body}>
        {look.backpack && (
          <g>
            <rect x={152} y={128} width={36} height={54} rx={12} fill="#6FB58F" stroke={LINE} strokeWidth={2.2} />
            <rect x={160} y={152} width={22} height={18} rx={5} fill="#8BCBA6" stroke={LINE} strokeWidth={1.6} />
          </g>
        )}

        {/* ears sit behind the body and follow the head */}
        <Pivot x={110} y={130} animate={head.animate} transition={head.transition}>
          <g transform="translate(-110 -130)">
            {[64, 156].map((x) => (
              <Pivot key={x} x={x} y={66} animate={{ rotate: x < 110 ? [-5, 3] : [5, -3] }} transition={loop(2.2)}>
                <circle cx={0} cy={-12} r={18} fill={FUR} stroke={LINE} strokeWidth={2.6} />
                <path d={x < 110 ? 'M-9,-4 A11,12 0 1 1 9,-16 Q0,-12 -9,-4 Z' : 'M9,-4 A11,12 0 1 0 -9,-16 Q0,-12 9,-4 Z'} fill="#D9A3A0" />
              </Pivot>
            ))}
          </g>
        </Pivot>

        {/* feet, pear body, cream muzzle and belly */}
        {[78, 142].map((x, i) => (
          <motion.g key={x} animate={running ? { x: i ? [8, -8] : [-8, 8], y: i ? [0, -5] : [-5, 0] } : { x: 0, y: 0 }} transition={running ? loop(0.16) : { duration: 0.2 }}>
            <ellipse cx={x} cy={205} rx={14} ry={5.5} fill={PAW} stroke={LINE} strokeWidth={2.2} />
          </motion.g>
        ))}
        <path d={PEAR} fill={FUR} stroke={LINE} strokeWidth={2.6} strokeLinejoin="round" />
        <g clipPath={`url(#${clip})`}>
          <ellipse cx={110} cy={118} rx={50} ry={24} fill={CREAM} />
          <ellipse cx={110} cy={176} rx={40} ry={27} fill={CREAM} />
          <rect x={98} y={130} width={24} height={30} fill={CREAM} />
          <ellipse cx={110} cy={146} rx={20} ry={5} fill="#F6D2B0" opacity={0.7} />
          <ellipse cx={52} cy={150} rx={12} ry={40} fill={FUR_DARK} opacity={0.3} />
          <ellipse cx={168} cy={150} rx={12} ry={40} fill={FUR_DARK} opacity={0.3} />
        </g>
        <path d="M100,45 l2,-6 M107,44 l1,-7 M114,44 l2,-6 M120,46 l3,-5" stroke={LINE} strokeWidth={2} strokeLinecap="round" />
        {look.backpack && <path d="M72,132 q-6,28 2,52 M148,132 q6,28 -2,52" stroke="#4E9A73" strokeWidth={5} fill="none" strokeLinecap="round" />}

        {/* head */}
        <Pivot x={110} y={130} animate={head.animate} transition={head.transition}>
          <g transform="translate(-110 -130)">
            {look.headphones && <path d="M56,84 Q56,26 110,26 Q164,26 164,84" stroke="#7A4B2A" strokeWidth={7} fill="none" strokeLinecap="round" />}
            <ellipse cx={70} cy={110} rx={9} ry={5} fill={PINK} opacity={0.4} />
            <ellipse cx={150} cy={110} rx={9} ry={5} fill={PINK} opacity={0.4} />
            {/* whiskers twitch */}
            <motion.path d="M78,103 L44,97 M78,110 L46,114 M142,103 L176,97 M142,110 L174,114" stroke={LINE} strokeWidth={1.5} strokeLinecap="round" fill="none" animate={{ opacity: [0.9, 0.9, 0.55, 0.9], y: [0, 0, 1, 0] }} transition={{ duration: 2.6, times: [0, 0.8, 0.9, 1], repeat: Infinity }} />
            <path d="M105,99 Q110,96.5 115,99 Q113,104.5 110,104.5 Q107,104.5 105,99 Z" fill="#F0A49A" />
            {p.mouth === 'o' ? (
              <ellipse cx={110} cy={112} rx={3.6} ry={4.4} fill="#7A3B33" />
            ) : p.mouth === 'talk' ? (
              <motion.ellipse cx={110} cy={112} rx={4.6} ry={3.6} fill="#7A3B33" animate={{ scaleY: [0.3, 1, 0.5, 1, 0.3] }} transition={{ duration: 0.7, repeat: Infinity }} />
            ) : p.mouth === 'smile' ? (
              <>
                <path d="M110,104.5 v4 M110,108.5 q-5,6 -10,2 M110,108.5 q5,6 10,2" stroke={INK} strokeWidth={2} fill="none" strokeLinecap="round" />
                <path d="M106.5,111 q3.5,5 7,0 Z" fill="#F0A49A" />
              </>
            ) : (
              <>
                <path d="M110,104.5 v4 M110,108.5 q-4,4 -8,2 M110,108.5 q4,4 8,2" stroke={INK} strokeWidth={2} fill="none" strokeLinecap="round" />
                <path d="M107.5,110.5 q2.5,3 5,0 Z" fill="#F0A49A" />
              </>
            )}

            {!hidden && (
              <>
                <Eye cx={86} mode={eyes} />
                <Eye cx={134} mode={eyes} />
              </>
            )}
            {p.brows === 'worried' && <path d="M77,76 L93,71 M143,76 L127,71" stroke={INK} strokeWidth={2.4} strokeLinecap="round" />}
            {p.brows === 'raised' && <path d="M78,74 q8,-6 15,-1 M127,73 q8,-5 15,1" stroke={INK} strokeWidth={2.2} fill="none" strokeLinecap="round" />}

            {look.glasses === 'round' && (
              <g stroke={INK} strokeWidth={2.6} fill="rgba(255,255,255,0.22)">
                <circle cx={86} cy={EYE_Y} r={15.5} />
                <circle cx={134} cy={EYE_Y} r={15.5} />
                <path d="M101.5,90 q8.5,-5 17,0" fill="none" />
                <motion.path d="M77,84 l5,-5" stroke="#fff" strokeWidth={2.2} strokeLinecap="round" animate={{ opacity: [0, 0.9, 0] }} transition={{ duration: 2.8, repeat: Infinity, repeatDelay: 1.2 }} />
              </g>
            )}
            {look.glasses === 'shades' && p.eyes !== 'closed' && (
              <g>
                <path d="M64,84 h92 v6 h-6 v6 h-6 v6 h-22 v-6 h-6 v-6 h-12 v6 h-6 v6 h-22 v-6 h-6 v-6 h-6 Z" fill="#17120F" />
                <motion.path d="M76,88 h6 v4 h4" stroke="#fff" strokeWidth={2} fill="none" animate={{ opacity: [0.2, 1, 0.2] }} transition={loop(1.6)} />
              </g>
            )}
            {look.headphones && (
              <>
                {[54, 166].map((x) => (
                  <g key={x}>
                    <rect x={x - 10} y={68} width={20} height={36} rx={9} fill="#9A5B33" stroke={LINE} strokeWidth={2.2} />
                    <rect x={x - 5} y={75} width={10} height={22} rx={5} fill="#C98859" />
                  </g>
                ))}
                {[0, 1].map((i) => (
                  <motion.text key={i} x={i ? 184 : 26} y={52} fontSize={15} fill="#4E9A73" animate={{ y: [56, 38], opacity: [0, 1, 0] }} transition={{ duration: 1.8, repeat: Infinity, delay: i * 0.9 }}>
                    ♪
                  </motion.text>
                ))}
              </>
            )}
            {look.sleepy &&
              [0, 1, 2].map((i) => (
                <motion.text key={i} x={158 + i * 9} y={40 - i * 10} fontSize={11 + i * 3} fontWeight={700} fill="#7A5FD0" animate={{ opacity: [0, 1, 0], y: [44 - i * 10, 36 - i * 10] }} transition={{ duration: 2.1, repeat: Infinity, delay: i * 0.45 }}>
                  z
                </motion.text>
              ))}

            {look.hat === 'grad' && (
              <g>
                <path d="M84,44 v9 q26,10 52,0 v-9 Z" fill="#2D3550" stroke={LINE} strokeWidth={1.6} />
                <polygon points="110,18 62,36 110,54 158,36" fill="#3A4466" stroke={LINE} strokeWidth={2} strokeLinejoin="round" />
                <Pivot x={110} y={36} animate={{ rotate: [-5, 5] }} transition={loop(1.2)}>
                  <path d="M0,0 L36,5 L36,22" stroke={GOLD} strokeWidth={2.2} fill="none" />
                  <rect x={33} y={21} width={6} height={10} rx={1.5} fill={GOLD} stroke="#9A6F0C" strokeWidth={0.8} />
                </Pivot>
              </g>
            )}
            {look.hat === 'crown' && (
              <Pivot x={110} y={48} animate={{ rotate: [-3, 3] }} transition={loop(1.8)}>
                <g transform="translate(-110 -48)">
                  <Crown />
                </g>
              </Pivot>
            )}
            {fx.includes('crown') && look.hat !== 'crown' && (
              <motion.g initial={{ y: -46, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ type: 'spring', stiffness: 220, damping: 11 }}>
                <Crown />
              </motion.g>
            )}
          </g>
        </Pivot>

        {/* things held in front */}
        {(prop === 'book' || prop === 'bookUp') && (
          <motion.g animate={{ y: prop === 'bookUp' ? -74 : 0 }} transition={{ type: 'spring', stiffness: 150, damping: 15 }}>
            <polyline points="77,150 109,155 111,155 143,150" stroke="#FFFDF8" strokeWidth={5} fill="none" strokeLinejoin="round" />
            <polygon points="75,152 109,157 109,192 75,187" fill="#5E9A6B" stroke={LINE} strokeWidth={2} strokeLinejoin="round" />
            <polygon points="145,152 111,157 111,192 145,187" fill="#5E9A6B" stroke={LINE} strokeWidth={2} strokeLinejoin="round" />
            <path d="M83,164 l18,2.4 M83,171 l12,1.6 M137,164 l-18,2.4 M137,171 l-12,1.6" stroke="#CFE6C8" strokeWidth={2} strokeLinecap="round" />
            {fx.includes('page') && (
              <g transform="translate(110 155)">
                <motion.path d="M0,0 L30,-5 L30,-1 L0,4 Z" fill="#FFFDF8" stroke="#D9CBB5" strokeWidth={0.6} animate={{ scaleX: [1, 1, -1, -1], opacity: [1, 1, 1, 0] }} transition={{ duration: 2.4, times: [0, 0.55, 0.85, 1], repeat: Infinity }} />
              </g>
            )}
          </motion.g>
        )}
        {prop === 'card' && (
          <motion.g animate={{ y: [0, -3, 0] }} transition={{ duration: 1.6, repeat: Infinity }}>
            <rect x={80} y={142} width={60} height={46} rx={8} fill="#FFFDF8" stroke={LINE} strokeWidth={2} />
            <text x={110} y={177} textAnchor="middle" fontSize={32} fontWeight={700} fill="#7A5FD0" fontFamily="Georgia, serif">
              ?
            </text>
          </motion.g>
        )}
        {prop === 'doc' && (
          <g>
            <path d="M86,136 h36 l12,12 v46 h-48 Z" fill="#FFFDF8" stroke={LINE} strokeWidth={2} strokeLinejoin="round" />
            <path d="M122,136 v12 h12" fill="#EADFCB" stroke={LINE} strokeWidth={1.6} strokeLinejoin="round" />
            <path d="M94,158 h30 M94,166 h32 M94,174 h24 M94,182 h28" stroke="#C9B79C" strokeWidth={2.2} strokeLinecap="round" />
            {fx.includes('scan') && <motion.rect x={86} width={48} height={3} rx={1.5} fill="#7A5FD0" opacity={0.7} animate={{ y: [140, 190] }} transition={loop(0.9)} />}
          </g>
        )}
        {prop === 'certificate' && (
          <g>
            <rect x={70} y={144} width={80} height={50} rx={3} fill="#FFFDF8" stroke={LINE} strokeWidth={2} />
            <rect x={75} y={149} width={70} height={40} fill="none" stroke={GOLD} strokeWidth={1.4} />
            <path d="M88,159 h44 M95,166 h30 M90,173 h24" stroke="#B8834A" strokeWidth={2} strokeLinecap="round" />
            <path d="M130,180 l-4,10 l4,-3 l4,3 Z" fill="#7A5FD0" />
            <circle cx={130} cy={178} r={6} fill={GOLD} stroke="#9A6F0C" strokeWidth={1} />
          </g>
        )}
        {look.laptop && !prop && (
          <g>
            <path d="M78,160 h64 l5,32 h-74 Z" fill="#B7BCC8" stroke={LINE} strokeWidth={2} strokeLinejoin="round" />
            <circle cx={110} cy={176} r={5} fill="#FFFDF8" />
            <motion.rect x={66} y={192} width={88} height={6} rx={3} fill="#8E94A3" stroke={LINE} strokeWidth={1.6} animate={{ opacity: [1, 0.85, 1] }} transition={loop(0.5)} />
          </g>
        )}

        {/* arms, with anything they hold */}
        <ArmGroup x={82} y={146} angle={look.laptop && !prop ? [-26, -18] : p.L} dur={look.laptop && !prop ? 0.18 : dur}>
          {prop === 'notebook' && (
            <g transform="translate(0 26) rotate(32)">
              <rect x={-8} y={-26} width={30} height={36} rx={3} fill="#FFFDF8" stroke={LINE} strokeWidth={1.8} />
              <path d="M-1,-17 h18 M-1,-10 h18 M-1,-3 h12" stroke="#C9B79C" strokeWidth={1.6} strokeLinecap="round" />
              <rect x={-8} y={-26} width={5} height={36} fill="#B58A5A" />
            </g>
          )}
        </ArmGroup>
        <ArmGroup x={138} y={146} angle={look.laptop && !prop ? [26, 18] : p.R} dur={look.laptop && !prop ? 0.21 : dur}>
          {prop === 'magnifier' && (
            <g>
              <line x1={0} y1={28} x2={0} y2={44} stroke={LINE} strokeWidth={6} strokeLinecap="round" />
              <circle cx={0} cy={58} r={14} fill="rgba(214,232,250,0.6)" stroke={LINE} strokeWidth={4} />
              <path d="M-7,53 q3,-6 9,-6" stroke="#fff" strokeWidth={2.2} fill="none" strokeLinecap="round" />
            </g>
          )}
          {(prop === 'notebook' || prop === 'gear') && (
            <g>
              <rect x={-2.8} y={20} width={5.6} height={28} rx={1} fill={GOLD} stroke={LINE} strokeWidth={1} />
              <path d="M-2.8,48 L0,57 L2.8,48 Z" fill={INK} />
            </g>
          )}
          {prop === 'pointer' && <line x1={0} y1={26} x2={0} y2={72} stroke="#8A5A2B" strokeWidth={3.4} strokeLinecap="round" />}
          {prop === 'badge' && (
            <g transform="translate(0 42) rotate(140)">
              <path d="M-7,-16 L0,-4 L7,-16" stroke="#7A5FD0" strokeWidth={5} fill="none" />
              <circle r={13} cy={6} fill={GOLD} stroke={LINE} strokeWidth={1.8} />
              <path d={STAR} transform="translate(0 6)" fill="#FFFDF8" />
            </g>
          )}
        </ArmGroup>
      </motion.g>
      </g>

      {!bust && p.bulb && <Bulb key={p.bulb} mode={p.bulb} x={inWheel ? 214 : 190} y={inWheel ? 4 : 36} />}
      {!bust && <Effects fx={fx} />}
    </svg>
  );
}

/** Circular profile picture: the same living hamster, cropped to head and shoulders. */
export function HamstarAvatar({ variant, size = 56, ring = true, state = 'idle' }: { variant?: MascotVariant; size?: number; ring?: boolean; state?: MascotState }) {
  const chosen = useStore((s) => s.profile.avatar);
  const v = variant ?? chosen;
  return (
    <span
      className="inline-flex items-end justify-center overflow-hidden rounded-full"
      style={{ width: size, height: size, background: (LOOKS[v] ?? LOOKS.reader).bg, boxShadow: ring ? '0 0 0 3px #fffdf6, 0 0 0 5px #f0c95a' : undefined, flexShrink: 0 }}
    >
      <HamstarMascot variant={v} state={state} bust size={size * 0.94} title={`${VARIANT_INFO[v]?.name ?? 'Reader'} hamster`} />
    </span>
  );
}

/** A hamster peeking over the top edge of whatever it is placed on. */
export function PeekingHamster({ size = 120, state = 'idle', variant, className = '' }: { size?: number; state?: MascotState; variant?: MascotVariant; className?: string }) {
  return (
    <span className={`inline-block shrink-0 overflow-hidden ${className}`} style={{ width: size, height: size * 0.74 }} aria-hidden>
      <HamstarMascot variant={variant} state={state} bust size={size} />
    </span>
  );
}
