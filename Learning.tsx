import { ArrowRight, Upload as UploadIcon } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { FolderTree } from '../components/FolderTree';
import { AppShell } from '../components/layout/AppShell';
import { QuestionTypeSelector } from '../components/QuestionTypeSelector';
import { ScorePanel } from '../components/ScorePanel';
import { StudyMaterialUpload } from '../components/StudyMaterialUpload';
import { HamstarMascot, type MascotState } from '../components/mascot/HamstarMascot';
import { useStore } from '../store/useStore';

/** The idea in four steps: a wrong answer is evidence, not a verdict. */
const STEPS: { title: string; text: string; state: MascotState; tint: string }[] = [
  { title: 'You answer', text: 'The exact answer you give is recorded, right or wrong.', state: 'question', tint: '#fdf1c9' },
  { title: 'I explain the answer', text: 'The correct answer, clearly. Ask for it again in simpler words any time.', state: 'explaining', tint: '#ece4fa' },
  { title: 'One sharp follow-up', text: 'A question on the same idea that tells a misconception from a slip.', state: 'investigating', tint: '#dcecc9' },
  { title: 'Then what I noticed', text: 'A diagnosis only above 70% confidence, never from one wrong answer.', state: 'thinking', tint: '#d9e6f6' },
];

export default function Learning() {
  // the parent folder under the pointer: the side panel shows its subfolders
  const [folder, setFolder] = useState<string | null>(null);
  const materials = useStore((s) => s.materials);
  // scores move with every answer, including ones given in a drill that was left half-way
  const refresh = useStore((s) => s.refresh);
  useEffect(() => {
    refresh().catch(() => {});
  }, [refresh]);

  return (
    <AppShell title="Learn" sub="Open a folder, or upload study material on any subject." aside={<ScorePanel folder={folder} />}>
      <section className="tile mb-3">
        <h2 className="mb-2 text-base">What kind of questions do you want?</h2>
        <QuestionTypeSelector />
      </section>

      <FolderTree onSelect={setFolder} />

      <section className="tile mt-3 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-lavender-soft">
            <UploadIcon size={24} className="text-lavender-deep" />
          </span>
          <div>
            <h2 className="text-lg leading-tight">Your study material</h2>
            <p className="text-sm text-ink-soft">
              {materials.length ? `${materials.length} file${materials.length === 1 ? '' : 's'} uploaded. I file each one in its folder for you.` : 'PDFs, slides, images or notes on any subject. I read them and file them in the right folder.'}
            </p>
          </div>
        </div>
        <Link to="/upload" className="btn btn-lilac">
          Upload material <ArrowRight size={18} />
        </Link>
      </section>

      <section className="mt-3">
        <h2 className="mb-2 text-base">Detect the misconception, not just the wrong answer</h2>
        <ol className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {STEPS.map((step, i) => (
            <li key={step.title} className="tile flex flex-col items-center text-center" style={{ backgroundColor: step.tint }}>
              <HamstarMascot state={step.state} size={104} />
              <div className="mt-1 text-sm font-extrabold">
                {i + 1}. {step.title}
              </div>
              <p className="text-xs text-ink-soft">{step.text}</p>
            </li>
          ))}
        </ol>
      </section>
    </AppShell>
  );
}

export function Upload() {
  const navigate = useNavigate();
  // "Upload more questions in <subject>" and "Add another document to <subfolder>" arrive with the folder already chosen
  const [params] = useSearchParams();
  const subject = params.get('subject')?.slice(0, 80) ?? '';
  const parent = params.get('parent')?.slice(0, 80) ?? '';
  return (
    <AppShell title={subject ? `Upload more for ${subject}` : 'Upload study material'} sub="I will read it, file it in the right folder and line up the questions.">
      <div className="mx-auto max-w-3xl">
        <StudyMaterialUpload initialSubject={subject} initialParent={parent} onReady={(folder) => navigate(`/session/${folder}`)} />
      </div>
    </AppShell>
  );
}
