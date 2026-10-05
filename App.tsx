import { AnimatePresence, MotionConfig, motion } from 'framer-motion';
import { useEffect, useState } from 'react';
import { HashRouter, Navigate, Outlet, Route, Routes } from 'react-router-dom';
import { BADGES, BadgeArt } from './components/BadgeCard';
import { CertificateModal } from './components/CertificateCard';
import { HamstarMascot } from './components/mascot/HamstarMascot';
import Dashboard from './pages/Dashboard';
import Learning, { Upload } from './pages/Learning';
import Login from './pages/Login';
import Mistakes from './pages/Mistakes';
import Notes from './pages/Notes';
import Profile from './pages/Profile';
import { Practice, Retry, Session } from './pages/Session';
import Settings from './pages/Settings';
import Tasks from './pages/Tasks';
import { messageOf } from './api/client';
import { useStore } from './store/useStore';
import { RouteTransitions } from './components/layout/PageTransition';
import { confettiBurst } from './lib/celebrate';

/** A badge or the certificate has just been earned. */
function Celebration() {
  const next = useStore((s) => s.celebrations[0]);
  const dismiss = useStore((s) => s.dismissCelebration);
  const [showCertificate, setShowCertificate] = useState(false);
  // a new badge or the certificate: the big confetti
  useEffect(() => {
    if (next) confettiBurst(true);
  }, [next]);
  return (
    <>
      <AnimatePresence>
        {next && (
          <motion.div className="fixed inset-0 z-40 flex items-center justify-center bg-ink/50 p-4" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} role="dialog" aria-modal="true">
            <motion.div initial={{ scale: 0.85, rotate: -3 }} animate={{ scale: 1, rotate: -1 }} className="panel max-w-sm p-7 text-center">
              {next.kind === 'badge' && next.badge ? (
                <>
                  <div className="flex justify-center">
                    <BadgeArt id={next.badge} size={120} unlocked />
                  </div>
                  <h2 className="mt-4 text-2xl">{BADGES[next.badge].name}</h2>
                  <p className="text-ink-soft">{BADGES[next.badge].requirement}</p>
                </>
              ) : (
                <>
                  <div className="flex justify-center"><HamstarMascot state="certificate" size={170} /></div>
                  <h2 className="mt-2 text-2xl">Your certificate is unlocked!</h2>
                </>
              )}
              <div className="mt-5 flex justify-center gap-3">
                {next.kind === 'certificate' && (
                  <button
                    className="btn btn-primary"
                    onClick={() => {
                      dismiss();
                      setShowCertificate(true);
                    }}
                  >
                    See it
                  </button>
                )}
                <button className="btn btn-ghost" onClick={dismiss}>
                  Keep going
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
      <CertificateModal open={showCertificate} onClose={() => setShowCertificate(false)} />
    </>
  );
}

function SignedIn() {
  const signedIn = useStore((s) => s.signedIn);
  const ready = useStore((s) => s.ready);
  const refresh = useStore((s) => s.refresh);
  const [error, setError] = useState('');

  // the learning record lives on the server: load it once per sign-in
  useEffect(() => {
    if (!signedIn || ready) return;
    setError('');
    refresh().catch((e) => setError(messageOf(e)));
  }, [signedIn, ready, refresh]);

  if (!signedIn) return <Navigate to="/login" replace />;
  if (!ready) {
    return (
      <div className="room">
        <div className="panel flex flex-col items-center gap-3 px-10 py-8 text-center">
          <HamstarMascot state={error ? 'thinking' : 'reading'} size={170} variant="reader" />
          <p className={error ? 'max-w-xs font-bold' : 'text-ink-soft'}>{error || 'Opening your desk…'}</p>
          {error && (
            <button className="btn btn-primary" onClick={() => refresh().then(() => setError('')).catch((e) => setError(messageOf(e)))}>
              Try again
            </button>
          )}
        </div>
      </div>
    );
  }
  return (
    <>
      <Outlet />
      <Celebration />
    </>
  );
}

export default function App() {
  return (
    // people who ask their system for less motion get the calm version
    <MotionConfig reducedMotion="user">
    <HashRouter>
      <RouteTransitions>
        {(location) => (
      <Routes location={location}>
        <Route path="/login" element={<Login />} />
        <Route element={<SignedIn />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/profile" element={<Profile />} />
          <Route path="/learn" element={<Learning />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/mistakes" element={<Mistakes />} />
          <Route path="/mistakes/:id/retry" element={<Retry />} />
          <Route path="/tasks" element={<Tasks />} />
          <Route path="/upload" element={<Upload />} />
          <Route path="/session/:topic" element={<Session />} />
          <Route path="/practice" element={<Practice />} />
          <Route path="/notes" element={<Notes />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
        )}
      </RouteTransitions>
    </HashRouter>
    </MotionConfig>
  );
}
