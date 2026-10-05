import { motion } from 'framer-motion';
import { ArrowLeft, BookOpen, LayoutDashboard, ListChecks, NotebookPen, RotateCcw, Settings, UserRound } from 'lucide-react';
import { useEffect, useState, type CSSProperties, type ReactNode } from 'react';
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom';
import { useStore } from '../../store/useStore';
import { HamstarAvatar, HamstarMascot } from '../mascot/HamstarMascot';
import { ThemeToggle } from '../ThemeToggle';
import { TiaraCounter } from '../TiaraCounter';
import { Wordmark } from '../Wordmark';
import { Ambient } from './Ambient';
import { PageMotion } from './PageTransition';

/** Tints are the marker colours behind the active item. */
const NAV = [
  { to: '/', label: 'My Dashboard', icon: LayoutDashboard, tint: '#fbe3a1', tick: '#c98a1a' },
  { to: '/learn', label: 'Learn', icon: BookOpen, tint: '#d9ebc6', tick: '#4f7a3a' },
  { to: '/mistakes', label: 'Past Mistakes', icon: RotateCcw, tint: '#e3d8f8', tick: '#7a5fd0' },
  { to: '/notes', label: 'Notes', icon: NotebookPen, tint: '#f9d9d9', tick: '#b0504a' },
  { to: '/tasks', label: 'Tasks', icon: ListChecks, tint: '#d3e3f5', tick: '#2f5d9a' },
  { to: '/profile', label: 'My Profile', icon: UserRound, tint: '#fbe3a1', tick: '#c98a1a' },
  { to: '/settings', label: 'Settings', icon: Settings, tint: '#efe4cf', tick: '#7a4b22' },
];

function useNarrow() {
  const [narrow, setNarrow] = useState(() => window.matchMedia('(max-width: 720px)').matches);
  useEffect(() => {
    const mq = window.matchMedia('(max-width: 720px)');
    const on = () => setNarrow(mq.matches);
    mq.addEventListener('change', on);
    return () => mq.removeEventListener('change', on);
  }, []);
  return narrow;
}

export function Sprig({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 56" className={className} aria-hidden fill="none" stroke="#5f8a4a" strokeWidth="2" strokeLinecap="round">
      <path d="M20 54 C20 38 22 24 30 8" />
      <path d="M21 40 C8 38 5 28 6 22 C16 23 21 30 21 40Z" fill="#a9cc8b" />
      <path d="M24 26 C36 26 38 16 37 10 C28 11 24 17 24 26Z" fill="#bcd99f" />
    </svg>
  );
}

export { Wordmark } from '../Wordmark';

function Sidebar() {
  const stored = useStore((s) => s.sidebarCollapsed);
  const toggle = useStore((s) => s.toggleSidebar);
  const narrow = useNarrow();
  const collapsed = stored || narrow;

  return (
    <nav className="panel sidebar no-print" data-collapsed={collapsed} aria-label="Main">
      <div className={`flex items-center ${collapsed ? 'flex-col gap-2' : 'justify-between pl-2'}`}>
        <Link to="/" aria-label="HamSTAR home">
          <Wordmark compact={collapsed} size={collapsed ? 24 : 25} />
        </Link>
        {!narrow && (
          <button className="burger" onClick={toggle} aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'} aria-expanded={!collapsed}>
            <span />
            <span />
            <span />
          </button>
        )}
      </div>

      <div className="mt-5 flex-1">
        {NAV.map((n) => (
          <NavLink key={n.to} to={n.to} end={n.to === '/'} className="nav-item" title={n.label} style={{ '--tint': n.tint, '--tick': n.tick } as CSSProperties}>
            <n.icon strokeWidth={2.1} />
            {!collapsed && <span>{n.label}</span>}
          </NavLink>
        ))}
      </div>

      {/* the hamster keeps reading in the corner of the desk */}
      <div className={`mt-4 flex items-end ${collapsed ? 'justify-center' : 'gap-1'}`}>
        <HamstarMascot state="reading" size={collapsed ? 52 : 92} />
        {!collapsed && (
          <p className="hand mb-4 -rotate-6 text-center text-[1.05rem] leading-[1.05] text-lavender-deep">
            Small steps,
            <br />
            big dreams
          </p>
        )}
      </div>
    </nav>
  );
}

interface ShellProps {
  title: string;
  /** Change it to replay the page transition when the same page swaps its content. */
  stage?: string;
  sub?: string;
  children: ReactNode;
  aside?: ReactNode;
}

/** The desk: collapsible sidebar, the main sheet with its heading, and an optional right-hand sheet. */
export function AppShell({ title, sub, children, aside, stage }: ShellProps) {
  const navigate = useNavigate();
  const { pathname, key } = useLocation();
  // one step back, wherever the student came from; a page opened directly has nowhere to go back to, so: home
  const back = () => (key === 'default' ? navigate('/') : navigate(-1));
  return (
    <div className="desk">
      <Ambient />
      <div className="desk-inner">
        <Sidebar />
        <PageMotion className="flex min-w-0 flex-1 flex-col gap-3 xl:flex-row">
          <main className="panel relative min-w-0 flex-1 p-4 sm:p-6">
            <header className="mb-4 flex items-center justify-between gap-4">
              {pathname !== '/' && (
                <button onClick={back} aria-label="Go back" data-tip="Back" className="no-print grid h-10 w-10 shrink-0 cursor-pointer place-items-center rounded-full border-2 border-line bg-paper text-[#7a4b22] shadow-[0_2px_0_#e6d8bd] transition hover:-translate-x-0.5 hover:bg-gold-soft active:translate-y-0.5 active:shadow-none">
                  <ArrowLeft size={20} strokeWidth={2.4} />
                </button>
              )}
              <div className="min-w-0 flex-1">
                <h1 className="page-title sm:truncate max-sm:whitespace-normal">{title}</h1>
                {sub && <p className="mt-1 text-ink-soft max-sm:hidden">{sub}</p>}
              </div>
              <div className="no-print flex shrink-0 items-center gap-3">
                <ThemeToggle />
                <TiaraCounter className="!px-3 !py-1 !text-[0.95rem] font-bold max-sm:hidden" />
                <Link to="/profile" data-tip="My profile">
                  <HamstarAvatar size={42} />
                </Link>
              </div>
            </header>
            <motion.div key={stage} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3, ease: 'easeOut' }}>
              {children}
            </motion.div>
          </main>
          {/* the right-hand sheet stays in view while the main sheet scrolls, like the sidebar */}
          {aside && <aside className="panel aside-sticky flex shrink-0 flex-col gap-3 p-4 xl:w-[19rem]">{aside}</aside>}
        </PageMotion>
      </div>
    </div>
  );
}
