import confetti from 'canvas-confetti';

/** The warm HamSTAR colours. */
const COLORS = ['#F5C842', '#F4A261', '#E76F51', '#A8DADC', '#FFFFFF'];

/**
 * A confetti burst from the top-centre of the screen, about two seconds long. `big` is for the larger moments
 * (a finished set, a new badge). Skipped for people who ask their system for less motion.
 */
export function confettiBurst(big = false) {
  const base = { colors: COLORS, disableForReducedMotion: true, zIndex: 70, ticks: 160, gravity: 1.1, scalar: 0.95 };
  confetti({ ...base, particleCount: big ? 140 : 80, spread: big ? 110 : 75, startVelocity: big ? 48 : 40, origin: { x: 0.5, y: 0.22 } });
  if (big) {
    // two side cannons a moment later
    setTimeout(() => {
      confetti({ ...base, particleCount: 60, angle: 60, spread: 60, origin: { x: 0, y: 0.6 } });
      confetti({ ...base, particleCount: 60, angle: 120, spread: 60, origin: { x: 1, y: 0.6 } });
    }, 250);
  }
}
