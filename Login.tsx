import { motion, useIsPresent } from 'framer-motion';
import { ArrowLeft, ArrowRight, Eye, EyeOff, KeyRound, Lock, User } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import { Ambient } from '../components/layout/Ambient';
import { Wordmark } from '../components/Wordmark';
import { ThemeToggle } from '../components/ThemeToggle';
import { HamstarMascot } from '../components/mascot/HamstarMascot';
import { api, messageOf } from '../api/client';
import { useStore } from '../store/useStore';

// signin: the usual form · forgot: ask for the Study ID · reset: the emailed code and a new Secret Squeak
type Mode = 'signin' | 'forgot' | 'reset';

export default function Login() {
  const signedIn = useStore((s) => s.signedIn);
  // slides up and out when leaving for the dashboard
  const present = useIsPresent();
  const signIn = useStore((s) => s.signIn);
  const resetPassword = useStore((s) => s.resetPassword);
  const navigate = useNavigate();
  // the link in the reset email opens this page with the Study ID and the code filled in
  const [params] = useSearchParams();
  const [mode, setMode] = useState<Mode>(params.get('reset') ? 'reset' : 'signin');
  const [email, setEmail] = useState(params.get('reset') ?? '');
  const [code, setCode] = useState(params.get('code') ?? '');
  const [password, setPassword] = useState('');
  const [show, setShow] = useState(false);
  const [remember, setRemember] = useState(true);
  const [note, setNote] = useState('');
  // good news (a code is on its way) is shown in green, problems in red
  const [good, setGood] = useState(false);
  // "New to HamSTA+R?" switches the same form to creating an account
  const [create, setCreate] = useState(false);
  const [busy, setBusy] = useState(false);
  // While the password field has focus the hamster shuts its eyes and lifts the book over them.
  const [secret, setSecret] = useState(false);

  if (signedIn) return <Navigate to="/" replace />;

  const say = (text: string, ok = false) => {
    setNote(text);
    setGood(ok);
  };
  const go = (next: Mode) => {
    setMode(next);
    setPassword('');
    say('');
  };

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    say('');
    try {
      await fn();
    } catch (err) {
      say(messageOf(err));
    } finally {
      setBusy(false);
    }
  };

  const sendCode = () =>
    run(async () => {
      const r = await api.post<{ message: string; expires_in_minutes: number }>('/api/auth/forgot-password', { email: email.trim() });
      setCode('');
      setMode('reset');
      say(`${r.message} It works for ${r.expires_in_minutes} minutes.`, true);
    });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (mode === 'forgot') {
      if (!email.trim()) return say('Enter your Study ID and I will send a reset code to it.');
      return void sendCode();
    }
    if (mode === 'reset') {
      if (!code.trim() || password.length < 6) return say('Enter the 6-digit code from the email and a new Secret Squeak of 6 or more characters.');
      return void run(async () => {
        await resetPassword(email.trim(), code.trim(), password);
        navigate('/');
      });
    }
    if (!email.trim() || !password) return say('Enter your Study ID and Secret Squeak to continue.');
    void run(async () => {
      await signIn(email.trim(), password, create);
      navigate('/');
    });
  };

  const heading = mode === 'forgot' ? 'Forgot your secret squeak?' : mode === 'reset' ? 'Check your inbox!' : create ? 'Welcome, new Hamster!' : 'Hey, Brainy Hamster!';
  const hamster = secret ? 'password' : mode === 'forgot' ? 'thinking' : mode === 'reset' ? 'question' : 'reading';
  const caption = secret ? 'Not looking, promise!' : mode === 'forgot' ? 'It happens to the best hamsters.' : mode === 'reset' ? 'A code is scurrying to your inbox.' : 'Think · Explain · Grow';

  const passwordField = (label: string, placeholder: string, autoComplete: string) => (
    <>
      <label className="mt-4 block text-sm font-bold" htmlFor="squeak">
        {label}
      </label>
      <div className="field mt-1 flex items-center gap-3">
        <Lock size={20} className="shrink-0 text-ink-soft" />
        <input
          id="squeak"
          type={show ? 'text' : 'password'}
          autoComplete={autoComplete}
          className="w-full bg-transparent outline-none placeholder:text-[#b3a391]"
          placeholder={placeholder}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          onFocus={() => setSecret(true)}
          onBlur={() => setSecret(false)}
        />
        <button type="button" onClick={() => setShow(!show)} aria-label={show ? 'Hide password' : 'Show password'} className="cursor-pointer text-ink-soft">
          {show ? <Eye size={20} /> : <EyeOff size={20} />}
        </button>
      </div>
    </>
  );

  return (
    <div className="room">
      <Ambient />
      <motion.div initial={{ opacity: 0, y: 20 }} animate={present ? { opacity: 1, y: 0 } : { opacity: 0, y: -20 }} transition={{ duration: 0.3, ease: 'easeOut' }} className="panel relative grid w-full max-w-[66rem] overflow-hidden md:min-h-[34rem] md:grid-cols-[1.05fr_1fr]">
        <form onSubmit={submit} className="flex flex-col justify-center p-6 sm:px-12 sm:py-10" noValidate>
          <div className="flex items-start justify-between gap-3">
            <Wordmark size={40} />
            <ThemeToggle />
          </div>
          <h1 className="mt-5 text-[2rem] leading-tight text-[#46291b]">{heading}</h1>

          {mode === 'signin' && (
            <p className="mt-1 text-ink-soft">
              {create ? 'Already have an account?' : "Don't have an account?"}{' '}
              <button
                type="button"
                className="hand-link cursor-pointer font-bold"
                onClick={() => {
                  setCreate(!create);
                  say('');
                }}
              >
                {create ? 'Sign in instead' : 'New to HamSTA+R?'}
              </button>
            </p>
          )}
          {mode === 'forgot' && <p className="mt-1 text-ink-soft">No worries. Tell me your Study ID and I will email you a code to choose a new one.</p>}
          {mode === 'reset' && (
            <p className="mt-1 text-ink-soft">
              Enter the 6-digit code sent to <b className="text-ink">{email}</b>, then choose a new Secret Squeak.
            </p>
          )}

          {mode !== 'reset' && (
            <>
              <label className="mt-6 block text-sm font-bold" htmlFor="study-id">
                Study ID
              </label>
              <div className="field mt-1 flex items-center gap-3">
                <User size={20} className="shrink-0 text-ink-soft" />
                <input id="study-id" type="email" autoComplete="email" className="w-full bg-transparent outline-none placeholder:text-[#b3a391]" placeholder={mode === 'forgot' ? 'The mail you signed up with' : 'Enter your mail'} value={email} onChange={(e) => setEmail(e.target.value)} />
              </div>
            </>
          )}

          {mode === 'reset' && (
            <>
              <label className="mt-6 block text-sm font-bold" htmlFor="reset-code">
                Reset code
              </label>
              <div className="field mt-1 flex items-center gap-3">
                <KeyRound size={20} className="shrink-0 text-ink-soft" />
                <input id="reset-code" inputMode="numeric" autoComplete="one-time-code" maxLength={8} className="w-full bg-transparent text-lg tracking-[0.4em] outline-none placeholder:tracking-normal placeholder:text-[#b3a391]" placeholder="6-digit code" value={code} onChange={(e) => setCode(e.target.value.replace(/[^\d ]/g, ''))} />
              </div>
              {passwordField('New Secret Squeak', 'Choose a new password (6+ characters)', 'new-password')}
            </>
          )}

          {mode === 'signin' && (
            <>
              {passwordField('Secret Squeak', create ? 'Choose a password (6+ characters)' : 'Enter your password', create ? 'new-password' : 'current-password')}
              <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-sm">
                <label className="flex cursor-pointer items-center gap-2">
                  <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} className="h-4 w-4 accent-[#e0a81c]" />
                  Remember me
                </label>
                <button type="button" className="cursor-pointer font-bold text-[#c98a1a]" onClick={() => go('forgot')}>
                  Forgot your secret squeak?
                </button>
              </div>
            </>
          )}

          <button type="submit" disabled={busy} className="btn btn-primary mt-5 w-full !py-3 !text-[1.05rem]">
            {busy ? 'One moment…' : mode === 'forgot' ? 'Send my reset code' : mode === 'reset' ? 'Save my new Secret Squeak' : create ? 'Start learning' : 'Back to learning'} <ArrowRight size={18} />
          </button>

          {mode !== 'signin' && (
            <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-sm">
              <button type="button" className="inline-flex cursor-pointer items-center gap-1 font-bold text-ink-soft hover:text-ink" onClick={() => go('signin')}>
                <ArrowLeft size={15} /> Back to sign in
              </button>
              {mode === 'reset' && (
                <button type="button" className="cursor-pointer font-bold text-[#c98a1a]" disabled={busy} onClick={() => (email.trim() ? sendCode() : go('forgot'))}>
                  Send a new code
                </button>
              )}
            </div>
          )}

          <p className={`mt-3 min-h-5 text-sm font-semibold ${good ? 'text-sage-deep' : 'text-rose'}`} aria-live="polite">
            {note}
          </p>
        </form>

        <div className="relative flex flex-col items-center justify-center gap-2 bg-gold-soft/70 p-6 max-md:order-first max-md:py-4" style={{ backgroundImage: 'var(--grain)' }}>
          <div className="flex aspect-square w-[min(21rem,60vw)] items-center justify-center rounded-full bg-[#fbd77a] shadow-[0_0_0_4px_#fffdf6,0_0_0_7px_#f0c95a] max-md:w-44">
            <HamstarMascot variant="reader" state={hamster} size={290} className="max-md:!h-36 max-md:!w-36" title={secret ? 'The hamster covers its eyes with its book' : 'The hamster is reading'} />
          </div>
          <p className="hand mt-3 text-center text-[1.3rem] text-[#7a4b22]" aria-live="polite">
            {caption}
          </p>
        </div>
      </motion.div>
    </div>
  );
}
