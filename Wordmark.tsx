import { useId } from 'react';
import { HamstarMascot } from './mascot/HamstarMascot';

/** The tiara over the H. A band of light sweeps across it every few seconds and a sparkle winks at the top. */
function Tiara() {
  const clip = `tiara-${useId().replace(/:/g, '')}`;
  const shape = 'M6 30 L4 11 L15 20 L24 5 L33 20 L44 11 L42 30 Z';
  return (
    <svg className="wm-crown" viewBox="0 0 48 40" aria-hidden>
      <defs>
        <clipPath id={clip}>
          <path d={shape} />
          <rect x="5" y="29" width="38" height="7" rx="3" />
        </clipPath>
      </defs>
      <path d={shape} fill="#f6c94d" stroke="#6b3613" strokeWidth="2.6" strokeLinejoin="round" />
      <rect x="5" y="29" width="38" height="7" rx="3" fill="#e9a92c" stroke="#6b3613" strokeWidth="2.6" />
      <circle cx="4" cy="10" r="3.2" fill="#f6c94d" stroke="#6b3613" strokeWidth="2" />
      <circle cx="24" cy="4" r="3.4" fill="#f6c94d" stroke="#6b3613" strokeWidth="2" />
      <circle cx="44" cy="10" r="3.2" fill="#f6c94d" stroke="#6b3613" strokeWidth="2" />
      <ellipse cx="24" cy="21" rx="3.4" ry="4.4" fill="#e64b7a" stroke="#6b3613" strokeWidth="1.6" />
      <ellipse cx="23" cy="19.6" rx="1" ry="1.4" fill="#fff" opacity="0.85" />
      {/* the sweep of light, clipped to the tiara */}
      <g clipPath={`url(#${clip})`}>
        <rect className="wm-shine" x="-6" y="0" width="10" height="40" fill="#fffbe6" opacity="0.85" />
      </g>
      <path className="wm-glint" d="M38 1 L39.4 5 L43.5 6.3 L39.4 7.6 L38 11.6 L36.6 7.6 L32.5 6.3 L36.6 5 Z" fill="#fff8d6" stroke="#f2b52b" strokeWidth="0.8" />
    </svg>
  );
}

/**
 * The HamSTA+R logo: bubbly letters, a shining tiara on the H, and the whole hamster standing beside the H
 * with one paw resting on it, leaning in now and then like it owns the place. `compact` keeps the hamster and
 * the H only (for the collapsed sidebar). `size` is the letter height in px.
 */
export function Wordmark({ compact = false, size = 26 }: { compact?: boolean; size?: number }) {
  return (
    <span className="wordmark" style={{ fontSize: size }} role="img" aria-label="HamSTAR">
      <span className="wm-h">
        <span className="wm-stand" aria-hidden>
          <HamstarMascot state="attitude" size={size * 1.3} />
        </span>
        <Tiara />
        <span className="wm-l">H</span>
      </span>
      {!compact && (
        <>
          <span className="wm-l cream">am</span>
          <span className="wm-l">ST</span>
          <span className="wm-a">
            <span className="wm-l">A</span>
            <span className="wm-l wm-plus">+</span>
          </span>
          <span className="wm-l">R</span>
        </>
      )}
    </span>
  );
}
