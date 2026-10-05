import { AnimatePresence, motion } from 'framer-motion';
import { Moon, Sun } from 'lucide-react';
import { useTheme } from '../lib/theme';

/** 🌙 / ☀️: switches between the sunny study desk and the same desk at night. Remembered in this browser. */
export function ThemeToggle({ className = '' }: { className?: string }) {
  const [theme, setTheme] = useTheme();
  const dark = theme === 'dark';
  return (
    <button className={`theme-toggle ${className}`} onClick={() => setTheme(dark ? 'light' : 'dark')} aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'} aria-pressed={dark} data-tip={dark ? 'Light mode' : 'Dark mode'}>
      <AnimatePresence mode="wait" initial={false}>
        <motion.span key={theme} initial={{ rotate: -90, scale: 0.4, opacity: 0 }} animate={{ rotate: 0, scale: 1, opacity: 1 }} exit={{ rotate: 90, scale: 0.4, opacity: 0 }} transition={{ duration: 0.22 }} className="grid place-items-center">
          {dark ? <Sun size={19} strokeWidth={2.3} /> : <Moon size={18} strokeWidth={2.3} />}
        </motion.span>
      </AnimatePresence>
    </button>
  );
}
