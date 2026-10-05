import { ArrowDownUp, BellRing, CalendarClock, ChevronDown, Plus, Star, Trash2, X } from 'lucide-react';
import { useEffect, useState, type CSSProperties, type FormEvent } from 'react';
import { AppShell } from '../components/layout/AppShell';
import { ScorePanel } from '../components/ScorePanel';
import type { TopicId } from '../api/types';
import { useFolders } from '../data/topics';
import { useStore, type Task } from '../store/useStore';

const BLUE = { '--wash': '#cfe3f7', '--edge': '#b4d0ee' } as CSSProperties;
const DAY = 86_400_000;
const midnight = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
const pad = (n: number) => String(n).padStart(2, '0');
/** A date as the value of a datetime-local input, in the student's own time zone. */
const local = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;

/** "Due tomorrow!", "Due in 2 days", "Overdue": neutral while there is time, amber as it nears, red at the end. */
export function dueInfo(deadline: string, done: boolean, now = new Date()) {
  const d = new Date(deadline);
  const when = d.toLocaleString(undefined, { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
  const days = Math.round((midnight(d) - midnight(now)) / DAY);
  if (done) return { label: `Was due ${d.toLocaleDateString(undefined, { day: 'numeric', month: 'short' })}`, tone: 'bg-white/60 text-ink-soft', when };
  if (d.getTime() < now.getTime()) return { label: days === 0 ? 'Overdue today' : `Overdue by ${-days} day${days === -1 ? '' : 's'}`, tone: 'bg-[#f6c5bf] text-[#a12d24]', when };
  if (days === 0) return { label: 'Due today!', tone: 'bg-[#f6c5bf] text-[#a12d24]', when };
  if (days === 1) return { label: 'Due tomorrow!', tone: 'bg-[#fbd9a8] text-[#a85a12]', when };
  if (days <= 3) return { label: `Due in ${days} days`, tone: 'bg-gold-soft text-gold-deep', when };
  return { label: `Due in ${days} days`, tone: 'bg-white/70 text-ink-soft', when };
}

function Row({ task }: { task: Task }) {
  const toggle = useStore((s) => s.toggleTask);
  const star = useStore((s) => s.starTask);
  const remove = useStore((s) => s.removeTask);
  const setDeadline = useStore((s) => s.setTaskDeadline);
  const [editing, setEditing] = useState(false);
  const due = task.deadline ? dueInfo(task.deadline, task.done) : null;

  return (
    <li className="group py-2">
      <div className="flex items-center gap-3 sm:gap-4">
        <button
          onClick={() => toggle(task.id)}
          aria-label={task.done ? `Mark ${task.title} as not done` : `Mark ${task.title} as done`}
          className={`flex h-7 w-7 shrink-0 cursor-pointer items-center justify-center rounded-full border-[3px] border-[#1d3557] text-white ${task.done ? 'bg-[#1d3557]' : 'bg-[#3f8fe6] hover:bg-[#62a6ee]'}`}
        >
          {task.done && '✓'}
        </button>
        <span className={`min-w-0 flex-1 text-[1.05rem] font-semibold leading-tight ${task.done ? 'text-ink-soft line-through' : ''}`}>{task.title}</span>
        {due && (
          <span className={`chip shrink-0 !py-0.5 text-xs font-bold ${due.tone}`} data-tip={`Deadline: ${due.when}${task.reminder_sent ? ' · reminder emailed' : ''}`}>
            {task.reminder_sent && !task.done && <BellRing size={12} className="mr-1 inline" />}
            {due.label}
          </span>
        )}
        {!task.done && (
          <button onClick={() => setEditing(!editing)} aria-label={task.deadline ? `Change the deadline of ${task.title}` : `Set a deadline for ${task.title}`} data-tip={task.deadline ? 'Change the deadline' : 'Set a deadline'} className={`cursor-pointer text-ink-soft transition hover:text-ink ${task.deadline ? '' : 'opacity-0 group-hover:opacity-100 focus:opacity-100 max-sm:opacity-100'}`}>
            <CalendarClock size={18} />
          </button>
        )}
        <button onClick={() => remove(task.id)} aria-label={`Delete ${task.title}`} className="cursor-pointer text-ink-soft opacity-0 transition group-hover:opacity-100 focus:opacity-100 max-sm:hidden">
          <Trash2 size={18} />
        </button>
        <button onClick={() => star(task.id)} aria-label={task.starred ? 'Remove star' : 'Add star'} aria-pressed={task.starred} className="cursor-pointer">
          <Star size={22} strokeWidth={1.8} className={task.starred ? 'fill-[#f6c94d] text-[#c9951a]' : 'fill-[#4a90e2] text-[#2f6fc0]'} />
        </button>
      </div>
      {editing && (
        <div className="ml-10 mt-1.5 flex flex-wrap items-center gap-2 text-sm">
          <input
            type="datetime-local"
            className="field !w-auto !py-1"
            aria-label={`Deadline for ${task.title}`}
            defaultValue={task.deadline ? local(new Date(task.deadline)) : ''}
            onChange={(e) => e.target.value && setDeadline(task.id, new Date(e.target.value).toISOString())}
          />
          {task.deadline && (
            <button className="inline-flex cursor-pointer items-center gap-1 font-bold text-ink-soft hover:text-ink" onClick={() => setDeadline(task.id, null).then(() => setEditing(false))}>
              <X size={14} /> No deadline
            </button>
          )}
          <button className="cursor-pointer font-bold text-[#2f5d9a]" onClick={() => setEditing(false)}>
            Done
          </button>
        </div>
      )}
    </li>
  );
}

export default function Tasks() {
  const tasks = useStore((s) => s.tasks);
  const addTask = useStore((s) => s.addTask);
  const loadTasks = useStore((s) => s.loadTasks);
  const remindersOn = useStore((s) => s.remindersOn);
  const email = useStore((s) => s.profile.email);
  const [starredFirst, setStarredFirst] = useState(false);
  const [showDone, setShowDone] = useState(false);
  const [title, setTitle] = useState('');
  const [date, setDate] = useState('');
  const [time, setTime] = useState('');
  const [error, setError] = useState('');
  const folders = useFolders();
  const [chosen, setTopic] = useState<TopicId>('');
  const topic = chosen || folders[0]?.id || 'General';
  // tasks filed under a folder that no longer exists still show, under their own name
  const groups = [...folders, ...[...new Set(tasks.map((t) => t.topic))].filter((id) => !folders.some((f) => f.id === id)).map((id) => ({ id, name: id }))];

  useEffect(() => {
    loadTasks().catch((e) => setError(e instanceof Error ? e.message : 'Your tasks could not be loaded.'));
  }, [loadTasks]);

  const open = tasks.filter((t) => !t.done);
  const done = tasks.filter((t) => t.done);
  // nearest deadline first within a folder; starred first when asked
  const order = (list: Task[]) =>
    [...list].sort((a, b) => (starredFirst ? Number(b.starred) - Number(a.starred) : 0) || (a.deadline ? Date.parse(a.deadline) : Infinity) - (b.deadline ? Date.parse(b.deadline) : Infinity));

  const add = async (e: FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;
    setError('');
    // a date with no time means the end of that day
    const deadline = date ? new Date(`${date}T${time || '23:59'}`).toISOString() : null;
    try {
      await addTask(title.trim(), topic, deadline);
      setTitle('');
      setDate('');
      setTime('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'That task could not be saved.');
    }
  };

  return (
    <AppShell title="Tasks" sub="Your goals, one task at a time." aside={<ScorePanel />}>
      <section className="stitch px-4 py-5 sm:px-8" style={BLUE}>
        <div className="mb-1 flex items-center justify-end">
          <button onClick={() => setStarredFirst(!starredFirst)} aria-pressed={starredFirst} title="Starred first" className={`cursor-pointer rounded-lg p-1.5 ${starredFirst ? 'bg-white/70' : ''}`}>
            <ArrowDownUp size={24} strokeWidth={2.6} />
          </button>
        </div>
        {groups.map(({ id: t, name }) => {
          const list = order(open.filter((x) => x.topic === t));
          if (!list.length) return null;
          return (
            <div key={t} className="mb-3">
              <h2 className="caps text-sm">{name}</h2>
              <ul className="pl-2 sm:pl-6">
                {list.map((task) => (
                  <Row key={task.id} task={task} />
                ))}
              </ul>
            </div>
          );
        })}
        {!open.length && <p className="py-4 text-center">No tasks yet. Add one below, for any of your folders.</p>}

        <form onSubmit={add} className="mt-2 flex flex-wrap items-end gap-2">
          <input className="field !w-auto min-w-[9rem] flex-1" placeholder="Add a task…" value={title} onChange={(e) => setTitle(e.target.value)} aria-label="New task" maxLength={200} />
          <select className="field !w-auto" value={topic} onChange={(e) => setTopic(e.target.value as TopicId)} aria-label="Folder">
            {folders.map((f) => (
              <option key={f.id} value={f.id}>
                {f.name}
              </option>
            ))}
          </select>
          <label className="text-xs font-bold">
            Deadline <span className="font-normal text-ink-soft">(optional)</span>
            <input type="date" className="field mt-0.5 block !w-auto" value={date} min={local(new Date()).slice(0, 10)} onChange={(e) => setDate(e.target.value)} aria-label="Deadline date" />
          </label>
          <label className="text-xs font-bold">
            Time <span className="font-normal text-ink-soft">(optional)</span>
            <input type="time" className="field mt-0.5 block !w-auto" value={time} disabled={!date} onChange={(e) => setTime(e.target.value)} aria-label="Deadline time" />
          </label>
          <button className="round-btn cursor-pointer" aria-label="Add task" disabled={!title.trim()}>
            <Plus size={22} />
          </button>
        </form>
        <p className="mt-2 flex items-center gap-1.5 text-xs text-ink-soft">
          <BellRing size={13} className="shrink-0" />
          {remindersOn ? `Give a task a deadline and I will squeak once, by email to ${email}, the day before. Finished tasks get no email.` : 'Deadlines and countdowns work now. Reminder emails start once email is set up on the server.'}
        </p>
        {error && <p className="mt-1 text-sm font-semibold text-rose">{error}</p>}
      </section>

      <section className="stitch mt-4 px-5 sm:px-8" style={BLUE}>
        <button className="flex w-full cursor-pointer items-center justify-between py-3 font-bold" onClick={() => setShowDone(!showDone)} aria-expanded={showDone}>
          Completed({done.length})
          <ChevronDown size={24} strokeWidth={2.6} className={`transition ${showDone ? 'rotate-180' : ''}`} />
        </button>
        {showDone && (
          <ul className="pb-3 pl-2 sm:pl-6">
            {done.map((task) => (
              <Row key={task.id} task={task} />
            ))}
          </ul>
        )}
      </section>
    </AppShell>
  );
}
