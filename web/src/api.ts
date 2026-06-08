import type {
  AiProvider,
  AiStatus,
  Album,
  ExportMode,
  ExportResult,
  ExportScope,
  Filters,
  Library,
  Photo,
  Series,
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
  library: () => request<Library>('/api/library'),

  photos: (f: Filters = {}) => {
    const q = new URLSearchParams()
    if (f.album) q.set('album', f.album)
    if (f.camera) q.set('camera', f.camera)
    if (f.keep) q.set('keep', f.keep)
    if (f.burstsOnly) q.set('bursts_only', 'true')
    const qs = q.toString()
    return request<Photo[]>(`/api/photos${qs ? `?${qs}` : ''}`)
  },

  series: () => request<Series[]>('/api/series'),

  thumb: (id: string) => `/api/thumb/${encodeURIComponent(id)}`,

  setKeep: (id: string, keep: boolean | null) =>
    request<{ ok: boolean }>(
      `/api/photos/${encodeURIComponent(id)}/keep`,
      json({ keep }),
    ),

  albums: () => request<Album[]>('/api/albums'),

  createAlbum: (name: string) =>
    request<{ ok: boolean }>('/api/albums', json({ name })),

  deleteAlbum: (name: string) =>
    request<{ ok: boolean }>(`/api/albums/${encodeURIComponent(name)}`, {
      method: 'DELETE',
    }),

  addToAlbum: (name: string, ids: string[]) =>
    request<{ ok: boolean }>(
      `/api/albums/${encodeURIComponent(name)}/photos`,
      json({ ids }),
    ),

  removeFromAlbum: (name: string, ids: string[]) =>
    request<{ ok: boolean }>(`/api/albums/${encodeURIComponent(name)}/photos`, {
      method: 'DELETE',
      body: JSON.stringify({ ids }),
      headers: { 'Content-Type': 'application/json' },
    }),

  reveal: (id: string) =>
    request<{ ok: boolean }>(`/api/reveal/${encodeURIComponent(id)}`, {
      method: 'POST',
    }),

  export: (scope: ExportScope, mode: ExportMode, outDir: string) =>
    request<ExportResult>('/api/export', json({ scope, mode, out_dir: outDir })),

  getAiSettings: () => request<AiStatus>('/api/settings/ai'),

  setAiSettings: (body: {
    provider: AiProvider
    api_key?: string
    base_url?: string
    model?: string
  }) => request<AiStatus>('/api/settings/ai', json(body)),

  search: (q: string) =>
    request<string[]>(`/api/search?q=${encodeURIComponent(q)}`),

  analyze: () => request<{ analyzed: number }>('/api/ai/analyze', { method: 'POST' }),
}
