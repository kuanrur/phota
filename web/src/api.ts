import type {
  DuplicateGroup,
  FinderArranged,
  FinderFoldersResponse,
  FinderTidyResult,
  IndexStatus,
  Library,
  OrganizeAction,
  OrganizeResult,
  RenameFmt,
  RenamePreview,
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

  /** Adopt `path` as the active folder and kick off an ASYNC (re)build of
   *  its index. Returns immediately with `indexing: true`; poll
   *  `indexStatus()` for progress. `~` expansion is handled server-side.
   *  Throws ApiError(409) when another index is already running. */
  openFolder: (path: string) =>
    request<{ folder: string; indexing: boolean }>(
      '/api/open-folder',
      json({ path }),
    ),

  /** Progress of the background index job started by `openFolder`. */
  indexStatus: () => request<IndexStatus>('/api/index-status'),

  /** Sets of near-identical photos in the active folder. */
  duplicates: () => request<DuplicateGroup[]>('/api/duplicates'),

  /** Run an organize action on the active folder. Throws ApiError on
   *  4xx (e.g. 409 destination collision, 400 unknown action) so the UI
   *  can surface the message. */
  organize: (action: OrganizeAction) =>
    request<OrganizeResult>('/api/organize', json({ action })),

  /** Reverse the last organize action; returns how many moves were undone. */
  undo: () => request<{ undone: number }>('/api/undo', { method: 'POST' }),

  /** Dry-run a batch rename under `fmt` (`word` only used for 'custom').
   *  `formats` filters to those file types (omit = all); an empty array is
   *  rejected server-side with 400. Returns the total affected and up to 3
   *  from→to examples; moves nothing. Throws ApiError on 400 (bad fmt /
   *  empty word / empty selection). */
  renamePreview: (fmt: RenameFmt, word?: string, formats?: string[]) =>
    request<RenamePreview>(
      '/api/rename',
      json({ fmt, word, formats, dry_run: true }),
    ),

  /** Apply a batch rename under `fmt`; `formats` filters to those file types
   *  (omit = all). Returns how many files were renamed. Throws ApiError on
   *  400 (bad fmt / empty word / empty selection) or 409 (collision). */
  renameApply: (fmt: RenameFmt, word?: string, formats?: string[]) =>
    request<{ renamed: number }>('/api/rename', json({ fmt, word, formats })),

  /** Tidy the active folder's Finder window: snap icons to a grid
   *  ('cleanup') or keep it arranged-by-name ('keep_on' / 'keep_off'). */
  finderTidy: (action: 'cleanup' | 'keep_on' | 'keep_off') =>
    request<FinderTidyResult>('/api/finder-tidy', json({ action })),

  /** Whether the active folder's Finder window is kept arranged-by-name. */
  finderArranged: () => request<FinderArranged>('/api/finder-tidy'),
}
