import type {
  DuplicateGroup,
  FinderFoldersResponse,
  Library,
} from './types'

/** Thrown for any non-2xx response; carries the HTTP status. */
export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
    this.name = 'ApiError'
  }
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    ...init,
    headers: {
      ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
      ...init?.headers,
    },
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      if (body && typeof body.detail === 'string') detail = body.detail
    } catch {
      /* ignore non-json error bodies */
    }
    throw new ApiError(res.status, detail)
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

const json = (data: unknown): RequestInit => ({
  method: 'POST',
  body: JSON.stringify(data),
})

export const api = {
  /** Summary of the active folder (folder is null when none is open). */
  library: () => request<Library>('/api/library'),

  /** Folders currently open in Finder; `error` flags a permission block. */
  finderFolders: () =>
    request<FinderFoldersResponse>('/api/finder-folders'),

  /** Adopt `path` as the active folder; (re)builds its index.
   *  `~` expansion is handled server-side. */
  openFolder: (path: string) =>
    request<{ folder: string; count: number }>('/api/open-folder', json({ path })),

  /** Sets of near-identical photos in the active folder. */
  duplicates: () => request<DuplicateGroup[]>('/api/duplicates'),
}
