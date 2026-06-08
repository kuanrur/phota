import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api, ApiError } from './api'
import type {
  AiStatus,
  Album,
  Filters,
  KeepFilter,
  Library,
  Photo,
  Series,
} from './types'
import { TopBar } from './components/TopBar'
import { AlbumRail } from './components/AlbumRail'
import { Grid } from './components/Grid'
import { ActionBar } from './components/ActionBar'
import { CullMode } from './components/CullMode'
import { Settings } from './components/Settings'
import { ExportDialog } from './components/ExportDialog'

export default function App() {
  const [library, setLibrary] = useState<Library | null>(null)
  const [albums, setAlbums] = useState<Album[]>([])
  const [aiStatus, setAiStatus] = useState<AiStatus | null>(null)
  const [photos, setPhotos] = useState<Photo[]>([])
  const [loading, setLoading] = useState(true)

  const [filters, setFilters] = useState<Filters>({})
  const [selection, setSelection] = useState<Set<string>>(new Set())

  // search is held separately from the photo filters because it is applied
  // either client-side (AI off) or by resolving a set of ids (AI on).
  const [searchText, setSearchText] = useState('')
  const [searchIds, setSearchIds] = useState<Set<string> | null>(null)
  const [searching, setSearching] = useState(false)

  const [cullOpen, setCullOpen] = useState(false)
  const [series, setSeries] = useState<Series[]>([])
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [exportOpen, setExportOpen] = useState(false)

  // id being dragged (carries whole selection when part of it)
  const dragId = useRef<string | null>(null)
  const lastSelected = useRef<string | null>(null)

  // ── Initial loads ──────────────────────────────────────────
  useEffect(() => {
    api.library().then(setLibrary).catch(() => setLibrary(null))
    api.albums().then(setAlbums).catch(() => setAlbums([]))
    api.getAiSettings().then(setAiStatus).catch(() => setAiStatus(null))
  }, [])

  // ── Refetch photos whenever non-search filters change ──────
  useEffect(() => {
    let cancelled = false
    // Standard data-fetching effect: flag loading, then resolve.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true)
    api
      .photos(filters)
      .then((p) => {
        if (!cancelled) setPhotos(p)
      })
      .catch(() => {
        if (!cancelled) setPhotos([])
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [filters])

  const refreshPhotos = useCallback(() => {
    api.photos(filters).then(setPhotos).catch(() => {})
  }, [filters])

  const refreshAlbums = useCallback(() => {
    api.albums().then(setAlbums).catch(() => {})
  }, [])

  // ── Search ─────────────────────────────────────────────────
  const runSearch = useCallback(async () => {
    const q = searchText.trim()
    if (!q) {
      setSearchIds(null)
      return
    }
    if (aiStatus?.configured) {
      setSearching(true)
      try {
        const ids = await api.search(q)
        setSearchIds(new Set(ids))
      } catch (e) {
        // 409 => not configured anymore; fall back to client filter
        if (e instanceof ApiError && e.status === 409) setSearchIds(null)
        else setSearchIds(new Set())
      } finally {
        setSearching(false)
      }
    } else {
      // client-side: handled in derived `visiblePhotos`
      setSearchIds(null)
    }
  }, [searchText, aiStatus])

  // Clear semantic-search results when the box is emptied.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (!searchText.trim()) setSearchIds(null)
  }, [searchText])

  // ── Derived visible photos (applies search) ────────────────
  const visiblePhotos = useMemo(() => {
    const q = searchText.trim().toLowerCase()
    if (aiStatus?.configured && searchIds) {
      // Preserve API ordering, keep only matched ids.
      return photos.filter((p) => searchIds.has(p.id))
    }
    if (q && !aiStatus?.configured) {
      return photos.filter(
        (p) =>
          p.filename.toLowerCase().includes(q) ||
          (p.camera?.toLowerCase().includes(q) ?? false) ||
          (p.captured_at?.toLowerCase().includes(q) ?? false),
      )
    }
    return photos
  }, [photos, searchText, searchIds, aiStatus])

  const keepCount = useMemo(
    () => photos.filter((p) => p.keep === true).length,
    [photos],
  )

  const photosById = useMemo(() => {
    const m = new Map<string, Photo>()
    for (const p of photos) m.set(p.id, p)
    return m
  }, [photos])

  // ── Filter setters ─────────────────────────────────────────
  const setCamera = (camera: string | undefined) =>
    setFilters((f) => ({ ...f, camera }))
  const setKeep = (keep: KeepFilter | undefined) =>
    setFilters((f) => ({ ...f, keep }))
  const toggleBursts = () =>
    setFilters((f) => ({ ...f, burstsOnly: !f.burstsOnly }))
  const setAlbum = (album: string | undefined) => {
    setFilters((f) => ({ ...f, album }))
    setSelection(new Set())
  }

  // ── Keep / reject (optimistic) ─────────────────────────────
  const applyKeep = useCallback(
    (id: string, keep: boolean | null) => {
      setPhotos((prev) => prev.map((p) => (p.id === id ? { ...p, keep } : p)))
      api.setKeep(id, keep).catch(() => refreshPhotos())
    },
    [refreshPhotos],
  )

  const keepSelected = useCallback(
    (keep: boolean | null) => {
      if (selection.size === 0) return
      const ids = [...selection]
      setPhotos((prev) =>
        prev.map((p) => (selection.has(p.id) ? { ...p, keep } : p)),
      )
      Promise.all(ids.map((id) => api.setKeep(id, keep))).catch(() =>
        refreshPhotos(),
      )
    },
    [selection, refreshPhotos],
  )

  // ── Selection ──────────────────────────────────────────────
  const onSelect = useCallback(
    (id: string, e: React.MouseEvent) => {
      setSelection((prev) => {
        const next = new Set(prev)
        if (e.shiftKey && lastSelected.current) {
          // Range select within currently visible list.
          const ids = visiblePhotos.map((p) => p.id)
          const a = ids.indexOf(lastSelected.current)
          const b = ids.indexOf(id)
          if (a >= 0 && b >= 0) {
            const [lo, hi] = a < b ? [a, b] : [b, a]
            for (let i = lo; i <= hi; i++) next.add(ids[i])
            return next
          }
        }
        if (e.metaKey || e.ctrlKey) {
          if (next.has(id)) next.delete(id)
          else next.add(id)
        } else {
          next.clear()
          next.add(id)
        }
        return next
      })
      lastSelected.current = id
    },
    [visiblePhotos],
  )

  const clearSelection = useCallback(() => setSelection(new Set()), [])

  // ── Drag → album ───────────────────────────────────────────
  const onDragStart = useCallback(
    (id: string) => {
      dragId.current = id
      // If dragging a tile not in the selection, treat it as a single drag.
      if (!selection.has(id)) setSelection(new Set([id]))
    },
    [selection],
  )

  const onDropOnAlbum = useCallback(
    async (name: string) => {
      const ids =
        dragId.current && !selection.has(dragId.current)
          ? [dragId.current]
          : [...selection]
      if (ids.length === 0) return
      try {
        await api.addToAlbum(name, ids)
      } finally {
        dragId.current = null
        refreshAlbums()
        // album membership changed; refresh photos so album chips reflect it
        refreshPhotos()
      }
    },
    [selection, refreshAlbums, refreshPhotos],
  )

  // ── Album CRUD ─────────────────────────────────────────────
  const createAlbum = useCallback(
    async (name: string) => {
      try {
        await api.createAlbum(name)
      } finally {
        refreshAlbums()
      }
    },
    [refreshAlbums],
  )

  const deleteAlbum = useCallback(
    async (name: string) => {
      try {
        await api.deleteAlbum(name)
      } finally {
        if (filters.album === name) setAlbum(undefined)
        refreshAlbums()
      }
    },
    [filters.album, refreshAlbums],
  )

  const onReveal = useCallback((id: string) => {
    api.reveal(id).catch(() => {})
  }, [])

  // ── Cull ───────────────────────────────────────────────────
  const openCull = useCallback(async () => {
    try {
      const s = await api.series()
      setSeries(s)
    } catch {
      setSeries([])
    }
    setCullOpen(true)
  }, [])

  const closeCull = useCallback(() => {
    setCullOpen(false)
    refreshPhotos()
  }, [refreshPhotos])

  // ── Grid-level keyboard shortcuts ──────────────────────────
  useEffect(() => {
    if (cullOpen || settingsOpen || exportOpen) return
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return
      if (e.key === 'k' || e.key === 'K') {
        if (selection.size) {
          e.preventDefault()
          keepSelected(true)
        }
      } else if (e.key === 'x' || e.key === 'X') {
        if (selection.size) {
          e.preventDefault()
          keepSelected(false)
        }
      } else if (e.key === 'Escape') {
        clearSelection()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [cullOpen, settingsOpen, exportOpen, selection, keepSelected, clearSelection])

  return (
    <div className="flex h-full flex-col">
      <TopBar
        library={library}
        aiStatus={aiStatus}
        filters={filters}
        searchText={searchText}
        onSearchText={setSearchText}
        onSubmitSearch={runSearch}
        searching={searching}
        onSetCamera={setCamera}
        onSetKeep={setKeep}
        onToggleBursts={toggleBursts}
        onOpenSettings={() => setSettingsOpen(true)}
      />

      <div className="flex min-h-0 flex-1">
        <AlbumRail
          albums={albums}
          activeAlbum={filters.album}
          totalCount={library?.count ?? 0}
          onSelectAlbum={setAlbum}
          onCreateAlbum={createAlbum}
          onDeleteAlbum={deleteAlbum}
          onDropOnAlbum={onDropOnAlbum}
        />

        <main className="min-w-0 flex-1 overflow-y-auto">
          <Grid
            photos={visiblePhotos}
            loading={loading}
            selection={selection}
            onSelect={onSelect}
            onKeep={applyKeep}
            onReveal={onReveal}
            onDragStart={onDragStart}
          />
        </main>
      </div>

      <ActionBar
        selectionCount={selection.size}
        keepCount={keepCount}
        visibleCount={visiblePhotos.length}
        onCull={openCull}
        onExport={() => setExportOpen(true)}
        onClearSelection={clearSelection}
      />

      {cullOpen && (
        <CullMode
          series={series}
          photosById={photosById}
          onKeep={applyKeep}
          onClose={closeCull}
        />
      )}

      {settingsOpen && (
        <Settings
          status={aiStatus}
          onClose={() => setSettingsOpen(false)}
          onSaved={setAiStatus}
        />
      )}

      {exportOpen && (
        <ExportDialog
          albums={albums}
          keepCount={keepCount}
          totalCount={library?.count ?? photos.length}
          onClose={() => setExportOpen(false)}
        />
      )}
    </div>
  )
}
