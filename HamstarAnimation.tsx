import { useEffect, useState, type ReactNode } from 'react';
import { HamstarMascot, type MascotState } from './HamstarMascot';

export interface AnimationStep {
  state: MascotState;
  /** How long to hold this state before moving on. The last step is held. */
  ms: number;
}

/** Plays a sequence of mascot states, e.g. analyse → confident → spin the wheel. */
export function HamstarAnimation({ steps, size = 130, onStep }: { steps: AnimationStep[]; size?: number; onStep?: (index: number) => void }) {
  const [i, setI] = useState(0);
  useEffect(() => {
    onStep?.(i);
    if (i >= steps.length - 1) return;
    const t = setTimeout(() => setI((x) => x + 1), steps[i].ms);
    return () => clearTimeout(t);
  }, [i]); // eslint-disable-line react-hooks/exhaustive-deps
  return <HamstarMascot state={steps[i].state} size={size} />;
}

/** The mascot with a speech bubble: the hamster is how HamSTAR talks to the student. */
export function MascotSays({
  state,
  children,
  size = 130,
  steps,
  onStep,
}: {
  state?: MascotState;
  children: ReactNode;
  size?: number;
  steps?: AnimationStep[];
  onStep?: (index: number) => void;
}) {
  return (
    <div className="flex items-end gap-3 sm:gap-4">
      {steps ? <HamstarAnimation steps={steps} size={size} onStep={onStep} /> : <HamstarMascot state={state} size={size} />}
      <div className="relative mb-4 max-w-lg rounded-3xl rounded-bl-md border-2 border-line bg-gold-soft px-4 py-2.5 leading-snug">
        {children}
      </div>
    </div>
  );
}
