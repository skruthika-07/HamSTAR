import { AnimatePresence, motion, useIsPresent } from 'framer-motion';
import type { ReactNode } from 'react';
import { useLocation } from 'react-router-dom';

const DURATION = 0.3;

/**
 * Keeps the page that is being left on screen just long enough for its content to slide out, then shows the
 * next one. The wrapper itself does not fade: only `PageMotion` inside it moves, so the sidebar and the desk
 * stay perfectly still between pages.
 */
export function RouteTransitions({ children }: { children: (location: ReturnType<typeof useLocation>) => ReactNode }) {
  const location = useLocation();
  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.div key={location.pathname} exit={{ opacity: 0.999 }} transition={{ duration: DURATION }}>
        {children(location)}
      </motion.div>
    </AnimatePresence>
  );
}

/** The part of a page that fades and slides in on arrival, and up and out on leaving. */
export function PageMotion({ children, className }: { children: ReactNode; className?: string }) {
  const present = useIsPresent();
  return (
    <motion.div className={className} initial={{ opacity: 0, y: 20 }} animate={present ? { opacity: 1, y: 0 } : { opacity: 0, y: -20 }} transition={{ duration: DURATION, ease: 'easeOut' }}>
      {children}
    </motion.div>
  );
}
