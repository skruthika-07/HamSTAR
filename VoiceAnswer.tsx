import { motion } from 'framer-motion';
import { Mic, Square } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

interface Props {
  onTranscript: (text: string) => void;
  onRecordingChange?: (recording: boolean) => void;
}

/** Speak an explanation. Uses the browser's built-in speech recognition where it exists. */
export function VoiceAnswer({ onTranscript, onRecordingChange }: Props) {
  const Recognition = typeof window !== 'undefined' ? ((window as any).SpeechRecognition ?? (window as any).webkitSpeechRecognition) : undefined;
  const [recording, setRecording] = useState(false);
  const [interim, setInterim] = useState('');
  const [error, setError] = useState('');
  const rec = useRef<any>(null);

  useEffect(() => () => rec.current?.abort?.(), []);

  const set = (on: boolean) => {
    setRecording(on);
    onRecordingChange?.(on);
  };

  const start = () => {
    if (!Recognition) {
      setError('Voice transcription is not available in this browser. Chrome or Edge support it, or you can type instead.');
      return;
    }
    setError('');
    const r = new Recognition();
    r.lang = 'en-US';
    r.interimResults = true;
    r.continuous = true;
    r.onresult = (e: any) => {
      let live = '';
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const text = e.results[i][0].transcript;
        if (e.results[i].isFinal) onTranscript(text.trim());
        else live += text;
      }
      setInterim(live);
    };
    r.onerror = (e: any) => {
      setError(e.error === 'not-allowed' ? 'Microphone access was blocked. Allow it in the browser to use voice.' : 'Could not hear anything. Try again or type instead.');
      set(false);
    };
    r.onend = () => {
      setInterim('');
      set(false);
    };
    rec.current = r;
    r.start();
    set(true);
  };

  return (
    <div className="flex flex-wrap items-center gap-3">
      <button type="button" onClick={recording ? () => rec.current?.stop() : start} className={`btn ${recording ? 'btn-dark' : 'btn-ghost'}`} aria-pressed={recording}>
        {recording ? <Square size={16} /> : <Mic size={16} />}
        {recording ? 'Stop' : 'Speak'}
      </button>
      {recording && (
        <span className="flex items-center gap-2 text-sm text-ink-soft" aria-live="polite">
          <span className="flex h-6 items-center gap-0.5">
            {[0, 1, 2, 3, 4].map((i) => (
              <motion.span key={i} className="w-1 rounded bg-lavender-deep" animate={{ height: [6, 22, 6] }} transition={{ duration: 0.7, repeat: Infinity, delay: i * 0.11 }} />
            ))}
          </span>
          {interim || 'Listening…'}
        </span>
      )}
      {error && <span className="text-sm text-rose">{error}</span>}
    </div>
  );
}
