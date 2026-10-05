import { useEffect, useState } from 'react';

export type Theme = 'light' | 'dark';
const KEY = 'hamstar-theme';

function stored(): Theme | null {
  try {
    const v = localStorage.getItem(KEY);
    return v === 'dark' || v === 'light' ? v : null;
  } catch {
    return null;
  }
}

/** The saved choice; the sunny light theme until the student picks dark. */
export function initialTheme(): Theme {
  return stored() ?? 'light';
}

export function applyTheme(theme: Theme) {
  document.documentElement.classList.toggle('dark', theme === 'dark');
}

const listeners = new Set<(t: Theme) => void>();
let current: Theme = 'light';

/** Called once before the first render, so a dark page never flashes light. */
export function startTheme() {
  current = initialTheme();
  applyTheme(current);
}

export function setTheme(theme: Theme) {
  current = theme;
  applyTheme(theme);
  try {
    localStorage.setItem(KEY, theme);
  } catch {
    // private mode: it still applies for this visit
  }
  listeners.forEach((f) => f(theme));
}

export function useTheme(): [Theme, (t: Theme) => void] {
  const [theme, set] = useState(current);
  useEffect(() => {
    listeners.add(set);
    return () => void listeners.delete(set);
  }, []);
  return [theme, setTheme];
}
