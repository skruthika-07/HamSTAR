import { useStore } from '../store/useStore';

export interface Folder {
  id: string;
  name: string;
}

/** Every folder the student has: the starter bank plus one per subject they have uploaded. Nothing is hard-coded. */
export function useFolders(): Folder[] {
  const topics = useStore((s) => s.topics);
  const materials = useStore((s) => s.materials);
  const out: Folder[] = topics.map((t) => ({ id: t.id, name: t.name }));
  for (const m of materials) if (!out.some((f) => f.name.toLowerCase() === m.subject.toLowerCase())) out.push({ id: m.subject, name: m.subject });
  return out;
}

/** The display name of a folder id or subject. Unknown ones are shown as they are. */
export function useFolderName(): (id: string) => string {
  const folders = useFolders();
  return (id) => folders.find((f) => f.id === id)?.name ?? id;
}
