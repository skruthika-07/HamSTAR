import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { api, getToken, setToken, setUnauthorizedHandler } from '../api/client';
import type { AvatarId, BadgeId, BadgeView, Dashboard, FolderTree, Material, RecurringSummary, Mistake, QuestionType, TopicId, TopicProgress, Unlock, UserView, WeakArea } from '../api/types';

export type { AvatarId, BadgeId, Material } from '../api/types';
export type MistakeRecord = Mistake;

export interface Task {
  id: string;
  title: string;
  topic: TopicId;
  done: boolean;
  starred: boolean;
  /** ISO time, or null for a task with no deadline. */
  deadline: string | null;
  /** True once the one reminder email for this task has gone out. */
  reminder_sent: boolean;
}

// the student writes their own, for whichever subjects they study
const DEFAULT_TASKS: Task[] = [];

export const TIARA_FOR_CERTIFICATE = 500;

export interface Stats {
  answered: number;
  correct: number;
  tiara: number;
  streak: number;
  bestStreak: number;
  noSkip: number;
  skipped: number;
  mistakesCorrected: number;
}

export type Celebration = Unlock;

interface State {
  signedIn: boolean;
  /** False until the first load from the server has finished. */
  ready: boolean;
  profile: { name: string; email: string; role: string; avatar: AvatarId };
  stats: Stats;
  totalConfidence: number;
  topics: TopicProgress[];
  weakAreas: WeakArea[];
  mistakes: MistakeRecord[];
  badges: BadgeView[];
  certificate: { id: string; at: number } | null;
  materials: Material[];
  /** Parent folders → subfolders → documents, with confidence and weakness. */
  folders: FolderTree;
  recurring: RecurringSummary;
  activity: { at: string; text: string }[];
  celebrations: Celebration[];
  // the student's own to-do list, kept with their account so deadlines can be reminded by email
  tasks: Task[];
  sidebarCollapsed: boolean;
  /** The kind of question the student has chosen to practise, and the marks for each kind. */
  questionType: QuestionType;
  questionMarks: Record<QuestionType, number>;
  /** The document the student is working on: questions come only from it. */
  activeDocument: string | null;
  /** Demo only: show every badge as unlocked. Nothing is awarded; leaving the preview shows the real ones again. */
  badgePreview: boolean;

  setActiveDocument: (id: string | null) => void;
  setBadgePreview: (on: boolean) => void;
  /** Put the folders in place as the server returned them (after a rename), without a reload. */
  setFolders: (tree: FolderTree) => void;

  setQuestionType: (type: QuestionType, marks?: number) => void;
  toggleSidebar: () => void;
  /** Whether the server can send reminder emails. */
  remindersOn: boolean;
  loadTasks: () => Promise<void>;
  toggleTask: (id: string) => Promise<void>;
  starTask: (id: string) => Promise<void>;
  addTask: (title: string, topic: TopicId, deadline?: string | null) => Promise<void>;
  setTaskDeadline: (id: string, deadline: string | null) => Promise<void>;
  removeTask: (id: string) => Promise<void>;

  /** Signs in, or creates the account when `create` is set. Throws ApiError with the server's message. */
  signIn: (email: string, password: string, create?: boolean) => Promise<void>;
  /** Sets a new Secret Squeak with the emailed code, and signs in. */
  resetPassword: (email: string, code: string, password: string) => Promise<void>;
  signOut: () => void;
  /** Reload everything shown outside the question flow from the server. */
  refresh: () => Promise<void>;
  updateProfile: (patch: Partial<Pick<UserView, 'name' | 'role' | 'avatar'>>) => void;
  celebrate: (unlocked: Unlock[] | undefined) => void;
  dismissCelebration: () => void;
  demo: (action: 'load' | 'reset' | 'add_tiara', amount?: number) => Promise<void>;
}

const emptyStats: Stats = { answered: 0, correct: 0, tiara: 0, streak: 0, bestStreak: 0, noSkip: 0, skipped: 0, mistakesCorrected: 0 };

const blank = {
  profile: { name: 'Student', email: '', role: 'Student', avatar: 'reader' as AvatarId },
  stats: emptyStats,
  totalConfidence: 0,
  topics: [] as TopicProgress[],
  weakAreas: [] as WeakArea[],
  mistakes: [] as MistakeRecord[],
  badges: [] as BadgeView[],
  certificate: null,
  materials: [] as Material[],
  folders: { folders: [], total_confidence: 0, average_score: null, suggestions: [] } as FolderTree,
  recurring: { recurring: [], patterns: [], logged: 0 } as RecurringSummary,
  activity: [] as { at: string; text: string }[],
  celebrations: [] as Celebration[],
};

let profileTimer: ReturnType<typeof setTimeout> | undefined;

/** Save one change to a task and show the task as the server now has it. */
async function patchTask(id: string, change: Partial<Pick<Task, 'done' | 'starred' | 'deadline'>>) {
  const saved = await api.patch<Task>(`/api/tasks/${id}`, change);
  useStore.setState((s) => ({ tasks: s.tasks.map((t) => (t.id === id ? saved : t)) }));
}

export const useStore = create<State>()(
  persist(
    (set, get) => ({
      signedIn: !!getToken(),
      ready: false,
      ...blank,
      tasks: DEFAULT_TASKS,
      sidebarCollapsed: false,
      questionType: 'MCQ',
      activeDocument: null,
      badgePreview: false,

      setActiveDocument: (id) => set({ activeDocument: id }),
      setBadgePreview: (on) => set({ badgePreview: on }),
      setFolders: (tree) => set({ folders: { folders: tree.folders, total_confidence: tree.total_confidence, average_score: tree.average_score, suggestions: tree.suggestions, hidden_starters: tree.hidden_starters ?? 0 }, totalConfidence: tree.total_confidence }),
      questionMarks: { ONE_WORD: 1, FILL_BLANK: 1, MCQ: 1, SHORT_ANSWER: 5, LONG_ANSWER: 15 },

      setQuestionType: (type, marks) => set((s) => ({ questionType: type, questionMarks: marks ? { ...s.questionMarks, [type]: marks } : s.questionMarks })),
      toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
      remindersOn: false,
      loadTasks: async () => {
        // tasks made before they moved to the server were kept in this browser: carry them over once
        const old = get().tasks.filter((t) => t.id.startsWith('t-'));
        for (const t of old) {
          const made = await api.post<Task>('/api/tasks', { title: t.title, topic: t.topic, starred: t.starred });
          if (t.done) await api.patch(`/api/tasks/${made.id}`, { done: true });
        }
        const r = await api.get<{ tasks: Task[]; reminders: boolean }>('/api/tasks');
        set({ tasks: r.tasks, remindersOn: r.reminders });
      },
      toggleTask: (id) => patchTask(id, { done: !get().tasks.find((t) => t.id === id)?.done }),
      starTask: (id) => patchTask(id, { starred: !get().tasks.find((t) => t.id === id)?.starred }),
      setTaskDeadline: (id, deadline) => patchTask(id, { deadline }),
      addTask: async (title, topic, deadline = null) => {
        const made = await api.post<Task>('/api/tasks', { title, topic, deadline });
        set((s) => ({ tasks: [...s.tasks, made] }));
      },
      removeTask: async (id) => {
        await api.del(`/api/tasks/${id}`);
        set((s) => ({ tasks: s.tasks.filter((t) => t.id !== id) }));
      },

      signIn: async (email, password, create = false) => {
        const session = await api.post<{ token: string; user: UserView }>(create ? '/api/auth/register' : '/api/auth/login', { email, password });
        setToken(session.token);
        set({ signedIn: true, ready: false });
        await get().refresh();
      },

      resetPassword: async (email, code, password) => {
        const session = await api.post<{ token: string; user: UserView }>('/api/auth/reset-password', { email, code, password });
        setToken(session.token);
        set({ signedIn: true, ready: false });
        await get().refresh();
      },

      signOut: () => {
        setToken(null);
        set({ signedIn: false, ready: false, activeDocument: null, badgePreview: false, tasks: [], ...blank });
      },

      refresh: async () => {
        const [d, m] = await Promise.all([api.get<Dashboard>('/api/dashboard'), api.get<{ mistakes: Mistake[] }>('/api/mistakes')]);
        set({
          ready: true,
          profile: { name: d.user.name, email: d.user.email, role: d.user.role, avatar: d.user.avatar },
          stats: { answered: d.stats.answered, correct: d.stats.correct, tiara: d.tiara.count, streak: d.streak.current, bestStreak: d.streak.longest, noSkip: d.streak.no_skip, skipped: d.stats.skipped, mistakesCorrected: d.stats.mistakes_corrected },
          totalConfidence: d.folders.total_confidence,
          topics: d.progress.topics,
          weakAreas: d.recommendations.weak_areas,
          mistakes: m.mistakes,
          badges: d.badges,
          certificate: d.certificate.unlocked && d.certificate.id ? { id: d.certificate.id, at: Date.parse(d.certificate.unlocked_at ?? '') || Date.now() } : null,
          materials: d.materials,
          folders: d.folders,
          recurring: d.recurring,
          activity: d.recent_activity,
        });
      },

      // shown at once, saved shortly after the last keystroke
      updateProfile: (patch) => {
        set((s) => ({ profile: { ...s.profile, ...patch } }));
        clearTimeout(profileTimer);
        profileTimer = setTimeout(() => {
          const { name, role, avatar } = get().profile;
          if (name.trim()) api.patch('/api/profile', { name, role, avatar }).catch(() => {});
        }, 500);
      },

      celebrate: (unlocked) => {
        if (unlocked?.length) set((s) => ({ celebrations: [...s.celebrations, ...unlocked] }));
      },
      dismissCelebration: () => set((s) => ({ celebrations: s.celebrations.slice(1) })),

      demo: async (action, amount) => {
        const r = await api.post<{ unlocked: Unlock[] }>('/api/demo', { action, amount });
        await get().refresh();
        get().celebrate(r.unlocked);
      },
    }),
    // the learning record lives on the server; only local preferences are kept in the browser
    { name: 'hamstar-v4', partialize: (s) => ({ sidebarCollapsed: s.sidebarCollapsed, questionType: s.questionType, questionMarks: s.questionMarks, activeDocument: s.activeDocument }) },
  ),
);

setUnauthorizedHandler(() => useStore.getState().signOut());
