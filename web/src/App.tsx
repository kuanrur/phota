import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api } from './api'
import type { DuplicateGroup, FinderFolder, Library, Photo } from './types'
import { FolderPicker } from './components/FolderPicker'
import { Grid } from './components/Grid'
import { ActionBar } from './components/ActionBar'
import { ArrowLeft, UndoIcon } from './components/icons'

/* ─────────────────────────────────────────────────────────────
   phota — finder-folder cleanup controller
   A small window that organizes the photo folder you have open
   in Finder. Two screens: a folder picker, and a drag-to-reorder
   grid that flags duplicates and sorts photos into subfolders.
   ───────────────────────────────────────────────────────────── */

type Screen = 'picker' | 'grid'

export default function App() {
  const [screen, setScreen] = useState<Screen>('picker')
  const [booting, setBooting] = useState(true)

  // ── Screen 1 state ─────────────────────────────────────────
  const [folders, setFolders] = useState<FinderFolder[]>([])
  const [foldersLoading, setFoldersLoading] = useState(false)
  const [busyPath, setBusyPath] = useState<string | null>(null)

  // ── Screen 2 state ─────────────────────────────────────────
  const [library, setLibrary] = useState<Library | null>(null)
  const [photos, setPhotos] = useState<Photo[]>([])
  const [dupes, setDupes] = useState<DuplicateGroup[]>([])
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [busy, setBusy] = useState(false)
  const [flash, setFlash] = useState<string | null>(null)

  // The on-disk order, captured each time we (re)load photos. The grid order
  // is "dirty" when `photos` no longer matches this baseline.
  const [baseline, setBaseline] = useState<string[]>([])
  const anchorRef = useRef<string | null>(null) // for shift-click ranges

  const showFlash = useCallback((msg: string) => {
    setFlash(msg)
    setTimeout(() => setFlash(null), 2400)
  }, [])

  // ── Loading ────────────────────────────────────────────────
  const loadFinderFolders = useCallback(() => {
    setFoldersLoading(true)
    api
      .finderFolders()
      .then(setFolders)
      .catch(() => setFolders([]))
      .finally(() => setFoldersLoading(false))
  }, [])

  const loadFolderData = useCallback(async () => {
    const [lib, ph, dup] = await Promise.all([
      api.library(),
      api.photos(),
      api.duplicates().catch(() => [] as DuplicateGroup[]),
    ])
    setLibrary(lib)
    setPhotos(ph)
    setDupes(dup)
    setBaseline(ph.map((p) => p.id))
    setSelected(new Set())
    anchorRef.current = null
    return lib
  }, [])

  // Reload only photos + duplicates after a disk mutation (folder unchanged).
  const reloadPhotos = useCallback(async () => {
    const [ph, dup, lib] = await Promise.all([
      api.photos(),
      api.duplicates().catch(() => [] as DuplicateGroup[]),
      api.library(),
    ])
    setPhotos(ph)
    setDupes(dup)
    setLibrary(lib)
    setBaseline(ph.map((p) => p.id))
    setSelected(new Set())
    anchorRef.current = null
  }, [])

  // ── Boot: jump to grid if a folder is already active ───────
  useEffect(() => {
    api
      .library()
      .then(async (lib) => {
        if (lib.folder) {
          await loadFolderData()
          setScreen('grid')
        } else {
          loadFinderFolders()
        }
      })
      .catch(() => loadFinderFolders())
      .finally(() => setBooting(false))
  }, [loadFolderData, loadFinderFolders])

  // ── Screen 1 → 2: adopt a folder ───────────────────────────
  const pickFolder = useCallback(
    async (path: string) => {
      setBusyPath(path)
      try {
        await api.openFolder(path)
        await loadFolderData()
        setScreen('grid')
      } catch {
        showFlash('could not open folder')
      } finally {
        setBusyPath(null)
      }
    },
    [loadFolderData, showFlash],
  )

  const backToPicker = useCallback(() => {
    setScreen('picker')
    setSelected(new Set())
    loadFinderFolders()
  }, [loadFinderFolders])

  // ── Duplicates derived sets ────────────────────────────────
  const dupeIds = useMemo(() => {
    const s = new Set<string>()
    for (const g of dupes) for (const id of g.ids) s.add(id)
    return s
  }, [dupes])

  // ── Order dirtiness ────────────────────────────────────────
  const orderDirty = useMemo(() => {
    if (baseline.length !== photos.length) return false
    return photos.some((p, i) => p.id !== baseline[i])
  }, [photos, baseline])

  // ── Local reorder (from drag) ──────────────────────────────
  const handleReorder = useCallback((orderedIds: string[]) => {
    setPhotos((prev) => {
      const byId = new Map(prev.map((p) => [p.id, p]))
      return orderedIds.map((id) => byId.get(id)!).filter(Boolean)
    })
  }, [])

  // ── Selection (click, shift-range, cmd/ctrl-toggle) ────────
  const handleSelectTile = useCallback(
    (id: string, e: React.MouseEvent) => {
      const ids = photos.map((p) => p.id)
      setSelected((prev) => {
        const next = new Set(prev)
        if (e.shiftKey && anchorRef.current) {
          const a = ids.indexOf(anchorRef.current)
          const b = ids.indexOf(id)
          if (a >= 0 && b >= 0) {
            const [lo, hi] = a < b ? [a, b] : [b, a]
            for (let i = lo; i <= hi; i++) next.add(ids[i])
          }
        } else if (e.metaKey || e.ctrlKey) {
          if (next.has(id)) next.delete(id)
          else next.add(id)
          anchorRef.current = id
        } else {
          // plain click: toggle, collapsing any multi-selection to just this.
          if (next.size === 1 && next.has(id)) {
            next.clear()
          } else {
            next.clear()
            next.add(id)
          }
          anchorRef.current = id
        }
        return next
      })
    },
    [photos],
  )

  const selectAllRepeats = useCallback(() => {
    setSelected(() => {
      const next = new Set<string>()
      for (const g of dupes)
        for (const id of g.ids) if (id !== g.keeper) next.add(id)
      return next
    })
  }, [dupes])

  // ── Disk mutations ─────────────────────────────────────────
  const applyOrder = useCallback(async () => {
    setBusy(true)
    try {
      const res = await api.reorder(photos.map((p) => p.id))
      await reloadPhotos()
      showFlash(`renamed ${res.renamed}`)
    } catch {
      showFlash('reorder failed')
    } finally {
      setBusy(false)
    }
  }, [photos, reloadPhotos, showFlash])

  const sortInto = useCallback(
    async (name: string) => {
      const ids = [...selected]
      if (ids.length === 0) return
      setBusy(true)
      try {
        const res = await api.sortInto(name, ids)
        await reloadPhotos()
        showFlash(`moved ${res.moved} → ${res.folder}`)
      } catch {
        showFlash('move failed (name taken?)')
      } finally {
        setBusy(false)
      }
    },
    [selected, reloadPhotos, showFlash],
  )

  const undo = useCallback(async () => {
    setBusy(true)
    try {
      const res = await api.undo()
      await reloadPhotos()
      showFlash(res.undone ? `undid ${res.undone}` : 'nothing to undo')
    } catch {
      showFlash('undo failed')
    } finally {
      setBusy(false)
    }
  }, [reloadPhotos, showFlash])

  // ── Render ─────────────────────────────────────────────────
  return (
    <div className="flex h-full justify-center bg-ink p-2">
      <div className="flex h-full w-full max-w-[980px] flex-col overflow-hidden rounded-[10px] border border-hairline bg-ink shadow-2xl">
        {booting ? (
          <div className="flex h-full items-center justify-center font-mono text-[12px] text-faint">
            loading…
          </div>
        ) : screen === 'picker' ? (
          <FolderPicker
            folders={folders}
            loading={foldersLoading}
            busyPath={busyPath}
            onPick={pickFolder}
            onReload={loadFinderFolders}
          />
        ) : (
          <>
            {/* ── Header ─────────────────────────────────────── */}
            <header className="flex items-center gap-4 border-b border-hairline px-5 py-3">
              <button
                onClick={backToPicker}
                className="flex flex-none items-center gap-1.5 font-mono text-[11px] text-dim transition-colors hover:text-text"
              >
                <ArrowLeft size={12} />
                folders
              </button>

              <div className="min-w-0 flex-1">
                <div className="truncate font-serif text-[16px] italic text-text">
                  {library?.folder
                    ? library.folder.replace(/\/+$/, '').split('/').pop()
                    : '—'}
                </div>
                <div className="flex items-center gap-2 truncate font-mono text-[10.5px] text-dim">
                  <span className="truncate">{library?.folder}</span>
                  <span className="flex-none text-faint">·</span>
                  <span className="flex-none text-faint">
                    {photos.length} photo{photos.length === 1 ? '' : 's'}
                  </span>
                </div>
              </div>

              <button
                onClick={undo}
                disabled={busy}
                className="flex flex-none items-center gap-1.5 border border-hairline px-2.5 py-1.5 font-sans text-[12px] text-text transition-colors hover:border-amber hover:text-amber disabled:cursor-default disabled:opacity-50"
              >
                <UndoIcon size={12} />
                Undo
              </button>
            </header>

            {/* ── Grid ───────────────────────────────────────── */}
            <Grid
              photos={photos}
              selected={selected}
              dupeIds={dupeIds}
              dupeGroupCount={dupes.length}
              onReorder={handleReorder}
              onSelectTile={handleSelectTile}
              onSelectAllRepeats={selectAllRepeats}
            />

            {/* ── Toolbar ────────────────────────────────────── */}
            <ActionBar
              selectedCount={selected.size}
              orderDirty={orderDirty}
              busy={busy}
              flash={flash}
              onApplyOrder={applyOrder}
              onSortInto={sortInto}
            />
          </>
        )}
      </div>
    </div>
  )
}
