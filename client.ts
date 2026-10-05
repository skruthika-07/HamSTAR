/** The one place the frontend talks to the HamSTAR backend. */
export const API_URL: string = (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8000';

const TOKEN_KEY = 'hamstar-token';

export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (token: string | null) => (token ? localStorage.setItem(TOKEN_KEY, token) : localStorage.removeItem(TOKEN_KEY));

export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

let onUnauthorized: () => void = () => {};
/** Called when the server says the session is no longer valid. */
export const setUnauthorizedHandler = (fn: () => void) => {
  onUnauthorized = fn;
};

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const form = body instanceof FormData;
  if (body !== undefined && !form) headers['Content-Type'] = 'application/json';

  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { method, headers, body: body === undefined ? undefined : form ? body : JSON.stringify(body) });
  } catch {
    throw new ApiError('NETWORK', 'Cannot reach the HamSTAR server. Is the backend running?', 0);
  }
  const json = await res.json().catch(() => null);
  if (!res.ok || !json?.success) {
    if (res.status === 401 && token) onUnauthorized();
    throw new ApiError(json?.error?.code ?? 'ERROR', json?.error?.message ?? 'Something went wrong.', res.status);
  }
  return json.data as T;
}

export const api = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, body ?? {}),
  patch: <T>(path: string, body: unknown) => request<T>('PATCH', path, body),
  del: <T>(path: string) => request<T>('DELETE', path),
  /** Send a form (a file upload) and report how much of it has gone, 0 to 1, as it goes. */
  upload: <T>(path: string, form: FormData, onProgress: (share: number) => void) =>
    new Promise<T>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open('POST', `${API_URL}${path}`);
      const token = getToken();
      if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`);
      xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(e.loaded / e.total);
      xhr.onerror = () => reject(new ApiError('NETWORK', 'Cannot reach the HamSTAR server. Is the backend running?', 0));
      xhr.onload = () => {
        let json: { success?: boolean; data?: T; error?: { code?: string; message?: string } } | null = null;
        try {
          json = JSON.parse(xhr.responseText);
        } catch {
          json = null;
        }
        if (xhr.status >= 200 && xhr.status < 300 && json?.success) return resolve(json.data as T);
        if (xhr.status === 401 && token) onUnauthorized();
        reject(new ApiError(json?.error?.code ?? 'ERROR', json?.error?.message ?? 'Something went wrong.', xhr.status));
      };
      xhr.send(form);
    }),
  /** Fetch a file (it needs the sign-in token, so a plain link will not do) and hand it to the browser to save. */
  download: async (path: string, filename: string) => {
    const token = getToken();
    let res: Response;
    try {
      res = await fetch(`${API_URL}${path}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
    } catch {
      throw new ApiError('NETWORK', 'Cannot reach the HamSTAR server. Is the backend running?', 0);
    }
    if (!res.ok) {
      const json = await res.json().catch(() => null);
      if (res.status === 401 && token) onUnauthorized();
      throw new ApiError(json?.error?.code ?? 'ERROR', json?.error?.message ?? 'The download did not work.', res.status);
    }
    const blob = await res.blob();
    if (!blob.size) throw new ApiError('EMPTY_FILE', 'The file came back empty. Please try again.', res.status);
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    // letting go of the link straight away can cancel the download in some browsers
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
  },
};

/** A fresh key per submission lets the server recognise a repeated request and not reward it twice. */
export const clientKey = () => crypto.randomUUID().replace(/-/g, '');

export const messageOf = (e: unknown) => (e instanceof Error ? e.message : 'Something went wrong.');
