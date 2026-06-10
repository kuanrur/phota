import { useCallback, useEffect, useRef, useState } from 'react'
import { api, ApiError } from './api'
import type {
  DuplicateGroup,
  FinderFolder,
  IndexStatus,
  Library,
  RenameFmt,
} from './types'
import { ArrowLeft, FolderIcon } from './components/icons'

/* ─────────────────────────────────────────────────────────────
   phota — minimal Finder-folder controller.

   A tiny utility window with three states:
     A · Picker     — choose a folder (from Finder, or a pasted path)
     · Indexing     — the chosen folder is being scanned (progress bar)
     B · Controlling — show ONLY which folder is selected
   No photo grid, no thumbnails. Just the selected folder.
   ───────────────────────────────────────────────────────────── */

type Screen = 'picker' | 'indexing' | 'folder'

/** What the indexing view renders while a folder is being scanned. */
interface Indexing {
  folder: string
  status: IndexStatus | null
  error: string | null
}

/** A finished, empty status — used to synthesize a fatal open-folder error. */
const EMPTY_STATUS: IndexStatus = {
  running: false,
  done: 0,
  total: 0,
  folder: null,
  count: null,
  error: null,
}

/** Repeats beyond the single keeper in each group — the number "Find
 *  duplicates" would move into _duplicates/. */
function extrasOf(groups: DuplicateGroup[]): number {
  return groups.reduce((sum, g) => sum + Math.max(g.ids.length - 1, 0), 0)
}

export default function App() {
  const [screen, setScreen] = useState<Screen>('picker')
  const [booting, setBooting] = useState(true)

  // ── State A — picker ───────────────────────────────────────
  const [folders, setFolders] = useState<FinderFolder[]>([])
  const [finderError, setFinderError] = useState<string | null>(null)
  const [scanning, setScanning] = useState(false)
  const [manualPath, setManualPath] = useState('')
  const [pickError, setPickError] = useState<string | null>(null)

  // ── Indexing — the chosen folder is being scanned ──────────
  const [indexing, setIndexing] = useState<Indexing | null>(null)

  // ── State B — controlling ──────────────────────────────────
  const [library, setLibrary] = useState<Library | null>(null)
  const [dupeGroups, setDupeGroups] = useState<number>(0)
  // Count of duplicate *extras* (repeats beyond the one kept per group).
  const [dupeExtras, setDupeExtras] = useState<number>(0)

  // ── Picker: (re)scan Finder ────────────────────────────────
  const scanFinder = useCallback(() => {
    setScanning(true)
    api
      .finderFolders()
      .then((res) => {
        setFolders(res.folders)
        setFinderError(res.error)
      })
      .catch(() => {
        setFolders([])
        setFinderError(null)
      })
      .finally(() => setScanning(false))
  }, [])

  // ── Controlling: load folder summary + duplicate count ─────
  const loadFolder = useCallback(async () => {
    const [lib, dupes] = await Promise.all([
      api.library(),
      api.duplicates().catch(() => []),
    ])
    setLibrary(lib)
    setDupeGroups(dupes.length)
    setDupeExtras(extrasOf(dupes))
  }, [])

  // ── Indexing: open a folder asynchronously and poll progress ─
  // A monotonically-increasing token so a stale poll from an earlier run
  // (e.g. the user changed folder mid-index) never resolves into State B.
  const runRef = useRef(0)

  const startIndexing = useCallback(
    (path: string) => {
      const folder = path.trim()
      if (!folder) return
      const run = ++runRef.current
      const stale = () => runRef.current !== run

      setScreen('indexing')
      setIndexing({ folder, status: null, error: null })

      // Has *our* (re)build actually been accepted? Until it has, a
      // running status belongs to a previous folder's index, so we must
      // not resolve into State B on its completion — we (re)issue
      // open-folder once it frees up.
      let accepted = false

      const tryOpen = async () => {
        if (stale() || accepted) return
        try {
          await api.openFolder(folder)
          if (stale()) return
          accepted = true
          // Our job is queued; drop any "still indexing previous" note.
          setIndexing((cur) => (cur ? { ...cur, error: null } : cur))
        } catch (e) {
          if (stale()) return
          if (e instanceof ApiError && e.status === 409) {
            // A previous index is still running — surface it and retry.
            setIndexing((cur) =>
              cur
                ? { ...cur, error: 'still indexing the previous folder…' }
                : cur,
            )
          } else {
            const msg =
              e instanceof ApiError ? e.message : 'could not open that folder'
            setIndexing((cur) =>
              cur
                ? {
                    ...cur,
                    status: { ...EMPTY_STATUS, error: msg },
                    error: msg,
                  }
                : cur,
            )
            accepted = true // stop retrying; a fatal error is shown
          }
        }
      }

      const poll = async () => {
        if (stale()) return
        try {
          const status = await api.indexStatus()
          if (stale()) return
          setIndexing((cur) => (cur ? { ...cur, status } : cur))

          if (!status.running) {
            // The previous index just drained — claim the slot for us.
            if (!accepted) {
              await tryOpen()
              if (!stale()) window.setTimeout(poll, 250)
              return
            }
            if (status.error) {
              setIndexing((cur) =>
                cur ? { ...cur, error: status.error } : cur,
              )
              return
            }
            await loadFolder()
            if (stale()) return
            setScreen('folder')
            setIndexing(null)
            return
          }
        } catch {
          /* transient fetch error — keep polling */
        }
        if (!stale()) window.setTimeout(poll, 250)
      }

      void tryOpen()
      window.setTimeout(poll, 250)
    },
    [loadFolder],
  )

  // ── Boot: refresh a stale index with visible progress ──────
  useEffect(() => {
    api
      .library()
      .then((lib) => {
        if (lib.folder) {
          // A folder is already active — re-open it so a stale index
          // refreshes with visible progress (re-opens are near-instant).
          startIndexing(lib.folder)
        } else {
          scanFinder()
        }
      })
      .catch(() => scanFinder())
      .finally(() => setBooting(false))
  }, [scanFinder, startIndexing])

  // ── Adopt a folder → Indexing → State B ────────────────────
  const open = useCallback(
    (path: string) => {
      if (!path.trim()) return
      setPickError(null)
      startIndexing(path)
    },
    [startIndexing],
  )

  // ── Back to State A — re-pick regardless of server's last folder ─
  const changeFolder = useCallback(() => {
    runRef.current++ // abandon any in-flight index poll
    setLibrary(null)
    setIndexing(null)
    setManualPath('')
    setPickError(null)
    setScreen('picker')
    scanFinder()
  }, [scanFinder])

  // ── Render ─────────────────────────────────────────────────
  return (
    <div className="flex h-full justify-center bg-ink p-2">
      <div className="flex h-full w-full max-w-[620px] flex-col overflow-hidden rounded-[10px] border border-hairline bg-ink shadow-2xl">
        {booting ? (
          <div className="flex h-full items-center justify-center font-mono text-[12px] text-faint">
            loading…
          </div>
        ) : screen === 'picker' ? (
          <Picker
            folders={folders}
            error={finderError}
            scanning={scanning}
            manualPath={manualPath}
            pickError={pickError}
            onManualChange={setManualPath}
            onPick={open}
            onRescan={scanFinder}
          />
        ) : screen === 'indexing' ? (
          <IndexingView state={indexing} onBack={changeFolder} />
        ) : (
          <Controller
            library={library}
            dupeGroups={dupeGroups}
            dupeExtras={dupeExtras}
            onChangeFolder={changeFolder}
            onReload={loadFolder}
          />
        )}
      </div>
    </div>
  )
}

/* ─── State A — Picker ───────────────────────────────────────── */

interface PickerProps {
  folders: FinderFolder[]
  error: string | null
  scanning: boolean
  manualPath: string
  pickError: string | null
  onManualChange: (v: string) => void
  onPick: (path: string) => void
  onRescan: () => void
}

function Picker({
  folders,
  error,
  scanning,
  manualPath,
  pickError,
  onManualChange,
  onPick,
  onRescan,
}: PickerProps) {
  const permission = error === 'permission'

  return (
    <div className="flex h-full items-center justify-center overflow-y-auto px-7 py-8">
      <div className="scale-in w-full max-w-[460px]">
        <h1 className="select-none font-serif text-[34px] italic leading-none text-text">
          phota
        </h1>
        <p className="mt-3 font-sans text-[13px] text-dim">
          pick a folder to organize
        </p>

        <div className="mt-7">
          {scanning ? (
            <div className="font-mono text-[12px] text-faint">reading Finder…</div>
          ) : permission ? (
            <div className="border border-hairline bg-panel px-5 py-5">
              <p className="font-sans text-[13px] leading-relaxed text-dim">
                phota needs permission to read your Finder folders. Open{' '}
                <span className="text-text">System Settings</span> →{' '}
                <span className="text-text">Privacy &amp; Security</span> →{' '}
                <span className="text-text">Automation</span> and allow your
                terminal (Terminal/iTerm) to control Finder, then rescan.
              </p>
              <button
                onClick={onRescan}
                className="mt-4 border border-hairline px-3 py-1.5 font-sans text-[12px] text-text transition-colors hover:border-amber hover:text-amber"
              >
                Rescan
              </button>
            </div>
          ) : folders.length === 0 ? (
            <div className="border border-hairline bg-panel px-5 py-5">
              <p className="font-sans text-[13px] leading-relaxed text-dim">
                No folder open in Finder. Open one, or paste a path below.
              </p>
              <button
                onClick={onRescan}
                className="mt-4 border border-hairline px-3 py-1.5 font-sans text-[12px] text-text transition-colors hover:border-amber hover:text-amber"
              >
                Rescan
              </button>
            </div>
          ) : (
            <>
              <ul className="flex flex-col gap-2">
                {folders.map((f, i) => (
                  <li
                    key={f.path}
                    className="tile-enter"
                    style={{ animationDelay: `${Math.min(i, 10) * 35}ms` }}
                  >
                    <button
                      onClick={() => onPick(f.path)}
                      className="group flex w-full items-center gap-3 border border-hairline bg-panel px-4 py-3 text-left transition-colors hover:border-amber-ring hover:bg-elevated"
                    >
                      <span className="flex-none text-dim transition-colors group-hover:text-amber">
                        <FolderIcon size={16} />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate font-sans text-[14px] text-text">
                          {f.name}
                        </span>
                        <span className="block truncate font-mono text-[10.5px] text-dim">
                          {f.path}
                        </span>
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
              <button
                onClick={onRescan}
                className="mt-5 font-mono text-[11px] text-faint transition-colors hover:text-dim"
              >
                ↻ rescan Finder
              </button>
            </>
          )}
        </div>

        {/* Manual fallback — always available. */}
        <div className="mt-8 border-t border-hairline pt-6">
          <form
            onSubmit={(e) => {
              e.preventDefault()
              onPick(manualPath)
            }}
            className="flex items-center gap-2"
          >
            <input
              type="text"
              value={manualPath}
              onChange={(e) => onManualChange(e.target.value)}
              placeholder="or paste a folder path"
              spellCheck={false}
              autoCapitalize="off"
              autoCorrect="off"
              className="settings-input flex-1"
            />
            <button
              type="submit"
              disabled={!manualPath.trim()}
              className="flex-none border border-hairline px-3.5 py-2 font-sans text-[12px] text-text transition-colors hover:border-amber hover:text-amber disabled:cursor-default disabled:opacity-40"
            >
              Open
            </button>
          </form>
          {pickError && (
            <p className="mt-2 font-mono text-[11px] text-amber">{pickError}</p>
          )}
        </div>
      </div>
    </div>
  )
}

/* ─── Indexing — the chosen folder is being scanned ─────────────
   A calm darkroom progress view: folder name + path, a hairline
   track with an amber fill (done / total), no spinner, no photos. */

interface IndexingViewProps {
  state: Indexing | null
  onBack: () => void
}

function IndexingView({ state, onBack }: IndexingViewProps) {
  const folder = state?.folder ?? ''
  const name = folder.replace(/\/+$/, '').split('/').pop() || folder || '—'
  const status = state?.status ?? null
  const error = state?.error ?? null

  const done = status?.done ?? 0
  const total = status?.total ?? 0
  // Treat a missing status as "still scanning": no width, no count.
  const running = status?.running ?? true
  const scanning = running && total === 0
  const pct = total > 0 ? Math.min(100, (done / total) * 100) : 0

  // A hard error (open-folder/build failed) — offer a way back.
  const fatal = error !== null && status?.error != null

  return (
    <div className="flex h-full flex-col items-center justify-center px-8 py-14">
      <div className="scale-in w-full max-w-[420px] text-center">
        <div
          className="truncate font-serif text-[30px] italic leading-tight text-text"
          title={name}
        >
          {name}
        </div>
        <div
          className="mx-auto mt-2 max-w-[480px] truncate font-mono text-[11px] text-dim"
          title={folder}
        >
          {folder}
        </div>

        {fatal ? (
          <div className="mt-10">
            <p className="font-mono text-[11px] text-amber">{error}</p>
            <button
              onClick={onBack}
              className="mt-4 border border-hairline px-3 py-1.5 font-sans text-[12px] text-text transition-colors hover:border-amber hover:text-amber"
            >
              ← back to picker
            </button>
          </div>
        ) : (
          <div className="mt-10">
            {/* Slim hairline track with an amber fill. */}
            <div
              className="h-[2px] w-full overflow-hidden bg-hairline"
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={total || undefined}
              aria-valuenow={total > 0 ? done : undefined}
            >
              <div
                className="h-full bg-amber"
                style={{ width: `${pct}%`, transition: 'width 200ms ease-out' }}
              />
            </div>

            <p className="mt-3 font-mono text-[11px] text-dim">
              {scanning ? (
                'scanning…'
              ) : (
                <>
                  indexing… {done} / {total} photos
                </>
              )}
            </p>

            {/* A transient 409 note while a previous index drains. */}
            {error && (
              <p className="mt-2 font-mono text-[11px] text-faint">{error}</p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

/* ─── State B — Controller (shows ONLY the selected folder) ──── */

interface ControllerProps {
  library: Library | null
  dupeGroups: number
  dupeExtras: number
  onChangeFolder: () => void
  onReload: () => Promise<void>
}

type Action = 'sort_by_date' | 'by_day' | 'by_camera' | 'duplicates'
type Busy = Action | 'undo' | 'rename' | 'tidy' | 'keep' | null

function Controller({
  library,
  dupeGroups,
  dupeExtras,
  onChangeFolder,
  onReload,
}: ControllerProps) {
  const folder = library?.folder ?? ''
  const name = folder.replace(/\/+$/, '').split('/').pop() || folder || '—'
  const count = library?.count ?? 0

  // null = idle; otherwise the action currently in flight (or 'undo').
  const [busy, setBusy] = useState<Busy>(null)
  const [status, setStatus] = useState<{ text: string; error: boolean } | null>(
    null,
  )
  const working = busy !== null

  // ── Rename panel — expanded inline under the "Rename all" row ─
  const [renameOpen, setRenameOpen] = useState(false)

  // ── Finder · keep-arranged toggle (seeded on folder load) ────
  const [arranged, setArranged] = useState(false)
  useEffect(() => {
    let live = true
    api
      .finderArranged()
      .then((r) => {
        if (live) setArranged(r.arranged === true)
      })
      .catch(() => {
        if (live) setArranged(false)
      })
    return () => {
      live = false
    }
  }, [folder])

  const run = useCallback(
    async (action: Action) => {
      setBusy(action)
      setStatus(null)
      try {
        const res = await api.organize(action)
        setStatus({ text: summarize(res), error: false })
        await onReload()
      } catch (e) {
        const code = e instanceof ApiError ? e.status : 0
        setStatus({
          text:
            code === 409
              ? 'Couldn’t organize: a name already exists (409).'
              : code === 400
                ? 'Couldn’t organize: unknown action (400).'
                : 'Couldn’t organize: something went wrong.',
          error: true,
        })
      } finally {
        setBusy(null)
      }
    },
    [onReload],
  )

  const undo = useCallback(async () => {
    setBusy('undo')
    setStatus(null)
    try {
      const { undone } = await api.undo()
      setStatus({
        text:
          undone === 0
            ? 'Nothing to undo.'
            : `Undid ${undone} move${undone === 1 ? '' : 's'}.`,
        error: false,
      })
      await onReload()
    } catch {
      setStatus({ text: 'Couldn’t undo.', error: true })
    } finally {
      setBusy(null)
    }
  }, [onReload])

  // ── Apply a batch rename, then refresh like any other action ──
  const applyRename = useCallback(
    async (fmt: RenameFmt, word: string) => {
      setBusy('rename')
      setStatus(null)
      try {
        const { renamed } = await api.renameApply(
          fmt,
          fmt === 'custom' ? word : undefined,
        )
        setStatus({
          text: `Renamed ${renamed} photo${renamed === 1 ? '' : 's'}.`,
          error: false,
        })
        setRenameOpen(false) // collapse the panel on success
        await onReload()
      } catch (e) {
        // Surface the server's 400/409 detail in the existing error spot.
        const msg =
          e instanceof ApiError
            ? e.message
            : 'something went wrong'
        setStatus({ text: `Couldn’t rename: ${msg}.`, error: true })
      } finally {
        setBusy(null)
      }
    },
    [onReload],
  )

  // ── Finder · snap icons to a tidy grid ───────────────────────
  const tidyIcons = useCallback(async () => {
    setBusy('tidy')
    setStatus(null)
    try {
      const { ok, error } = await api.finderTidy('cleanup')
      setStatus(
        ok
          ? { text: 'Icons tidied.', error: false }
          : { text: tidyErrorText(error), error: true },
      )
    } catch {
      setStatus({ text: 'Couldn’t tidy icons.', error: true })
    } finally {
      setBusy(null)
    }
  }, [])

  // ── Finder · keep the window arranged-by-name (on/off) ───────
  const toggleKeep = useCallback(async () => {
    const next = !arranged
    setBusy('keep')
    setStatus(null)
    try {
      const { ok, error } = await api.finderTidy(next ? 'keep_on' : 'keep_off')
      if (ok) {
        setArranged(next)
        setStatus({
          text: next ? 'Keeping arranged.' : 'No longer arranged.',
          error: false,
        })
      } else {
        setStatus({ text: tidyErrorText(error), error: true })
      }
    } catch {
      setStatus({ text: 'Couldn’t change arrangement.', error: true })
    } finally {
      setBusy(null)
    }
  }, [arranged])

  const rows: {
    action: Action
    label: string
    desc: string
    affects: number
    empty?: boolean
  }[] = [
    {
      action: 'sort_by_date',
      label: 'Sort by date',
      desc: 'rename oldest to newest (001_, 002_)',
      affects: count,
    },
    {
      action: 'by_day',
      label: 'Group by day',
      desc: 'into dated folders (2025-12-24/)',
      affects: count,
    },
    {
      action: 'by_camera',
      label: 'Group by camera',
      desc: 'into a folder per camera',
      affects: count,
    },
    {
      action: 'duplicates',
      label: 'Find duplicates',
      desc: 'move repeats into _duplicates/',
      affects: dupeExtras,
      empty: dupeExtras === 0,
    },
  ]

  return (
    <div className="relative flex h-full flex-col overflow-y-auto">
      {/* change-folder link, quietly in the corner */}
      <button
        onClick={onChangeFolder}
        className="absolute left-4 top-4 z-10 flex items-center gap-1.5 font-mono text-[11px] text-dim transition-colors hover:text-text"
      >
        <ArrowLeft size={12} />
        change folder
      </button>

      <div className="flex flex-1 flex-col items-center justify-center px-8 py-14">
        <div className="scale-in w-full max-w-[420px] text-center">
          <h1 className="select-none font-serif text-[22px] italic leading-none text-dim">
            phota
          </h1>

          <div
            className="mt-7 truncate font-serif text-[30px] italic leading-tight text-text"
            title={name}
          >
            {name}
          </div>
          <div
            className="mx-auto mt-2 max-w-[480px] truncate font-mono text-[11px] text-dim"
            title={folder}
          >
            {folder}
          </div>

          <p className="mt-8 font-mono text-[11px] text-faint">
            {count} photo{count === 1 ? '' : 's'}
            {dupeGroups > 0 && (
              <>
                {' · '}
                {dupeGroups} set{dupeGroups === 1 ? '' : 's'} of repeats
              </>
            )}
          </p>

          {/* ── Organize ─────────────────────────────────────── */}
          <div className="mt-10 text-left">
            <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-faint">
              Organize
            </div>

            <ul className="mt-3 border-t border-hairline">
              {rows.map((r) => {
                const disabled = working || r.empty
                return (
                  <li key={r.action}>
                    <button
                      onClick={() => run(r.action)}
                      disabled={disabled}
                      className="group flex w-full items-center gap-4 border-b border-hairline px-1 py-3 text-left transition-colors hover:bg-elevated disabled:cursor-default disabled:hover:bg-transparent"
                    >
                      <span className="min-w-0 flex-1">
                        <span className="block font-sans text-[13.5px] text-text transition-colors group-hover:text-amber group-disabled:text-dim">
                          {r.label}
                        </span>
                        <span className="mt-0.5 block truncate font-mono text-[10.5px] text-dim">
                          {r.desc}
                        </span>
                      </span>
                      <span className="flex-none font-mono text-[10.5px]">
                        {r.empty ? (
                          <span className="text-faint">none found</span>
                        ) : (
                          <span className="text-amber">{r.affects}</span>
                        )}
                      </span>
                    </button>
                  </li>
                )
              })}

              {/* Fifth row — opens an inline rename panel (no modal). */}
              <li>
                <button
                  onClick={() => setRenameOpen((v) => !v)}
                  disabled={working}
                  aria-expanded={renameOpen}
                  className="group flex w-full items-center gap-4 border-b border-hairline px-1 py-3 text-left transition-colors hover:bg-elevated disabled:cursor-default disabled:hover:bg-transparent"
                >
                  <span className="min-w-0 flex-1">
                    <span
                      className={`block font-sans text-[13.5px] transition-colors group-disabled:text-dim ${
                        renameOpen
                          ? 'text-amber'
                          : 'text-text group-hover:text-amber'
                      }`}
                    >
                      Rename all
                    </span>
                    <span className="mt-0.5 block truncate font-mono text-[10.5px] text-dim">
                      give every photo a clean name
                    </span>
                  </span>
                  <span className="flex-none font-mono text-[10.5px] text-dim">
                    {renameOpen ? '−' : '+'}
                  </span>
                </button>
                {renameOpen && (
                  <RenamePanel
                    busy={busy === 'rename'}
                    working={working}
                    onApply={applyRename}
                  />
                )}
              </li>
            </ul>

            {/* ── Finder ───────────────────────────────────────── */}
            <div className="mt-9">
              <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-faint">
                Finder
              </div>

              <ul className="mt-3 border-t border-hairline">
                <li>
                  <button
                    onClick={tidyIcons}
                    disabled={working}
                    className="group flex w-full items-center gap-4 border-b border-hairline px-1 py-3 text-left transition-colors hover:bg-elevated disabled:cursor-default disabled:hover:bg-transparent"
                  >
                    <span className="min-w-0 flex-1">
                      <span className="block font-sans text-[13.5px] text-text transition-colors group-hover:text-amber group-disabled:text-dim">
                        Tidy icons
                      </span>
                      <span className="mt-0.5 block truncate font-mono text-[10.5px] text-dim">
                        snap icons to an even grid, sorted
                      </span>
                    </span>
                  </button>
                </li>
                <li>
                  <button
                    onClick={toggleKeep}
                    disabled={working}
                    role="switch"
                    aria-checked={arranged}
                    className="group flex w-full items-center gap-4 border-b border-hairline px-1 py-3 text-left transition-colors hover:bg-elevated disabled:cursor-default disabled:hover:bg-transparent"
                  >
                    <span className="min-w-0 flex-1">
                      <span className="block font-sans text-[13.5px] text-text transition-colors group-hover:text-amber group-disabled:text-dim">
                        Keep arranged
                      </span>
                      <span className="mt-0.5 block truncate font-mono text-[10.5px] text-dim">
                        keep the window sorted by name
                      </span>
                    </span>
                    <span className="flex-none">
                      <Toggle on={arranged} />
                    </span>
                  </button>
                </li>
              </ul>
            </div>

            <div className="mt-4 flex items-center justify-between gap-3">
              <button
                onClick={undo}
                disabled={working}
                className="border border-hairline px-3 py-1.5 font-sans text-[12px] text-text transition-colors hover:border-amber hover:text-amber disabled:cursor-default disabled:opacity-40"
              >
                Undo last
              </button>

              <div className="min-w-0 flex-1 text-right">
                {working ? (
                  <span className="font-mono text-[11px] text-amber">Working…</span>
                ) : status ? (
                  <span
                    className={`font-mono text-[11px] ${
                      status.error ? 'text-amber' : 'text-dim'
                    }`}
                  >
                    {status.text}
                  </span>
                ) : null}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

/** Human-readable status line from an organize response. */
function summarize(res: {
  action: string
  renamed?: number
  moved?: number
  folders?: number
}): string {
  if (res.action === 'sort_by_date') {
    const n = res.renamed ?? 0
    return `Renamed ${n} file${n === 1 ? '' : 's'}.`
  }
  if (res.action === 'by_day' || res.action === 'by_camera') {
    const n = res.moved ?? 0
    const f = res.folders ?? 0
    return `Moved ${n} into ${f} folder${f === 1 ? '' : 's'}.`
  }
  // duplicates
  const n = res.moved ?? 0
  return n === 0
    ? 'No repeats to move.'
    : `Moved ${n} repeat${n === 1 ? '' : 's'}.`
}

/** Status text for a failed Finder-tidy action. A 'permission' error reuses
 *  the same System Settings guidance the picker shows for Finder access. */
function tidyErrorText(error?: string | null): string {
  if (error === 'permission') {
    return 'Allow your terminal to control Finder in System Settings → Privacy & Security → Automation.'
  }
  if (error === 'no-window') return 'Open this folder in a Finder window first.'
  return 'Couldn’t reach Finder.'
}

/* ─── Finder · minimal on/off toggle ────────────────────────────
   A hairline pill that fills amber when on; matches the darkroom feel. */

function Toggle({ on }: { on: boolean }) {
  return (
    <span
      className={`relative block h-[14px] w-[24px] rounded-full border transition-colors ${
        on ? 'border-amber-ring bg-amber-wash' : 'border-hairline bg-ink'
      }`}
    >
      <span
        className={`absolute top-[1px] h-[10px] w-[10px] rounded-full transition-all ${
          on ? 'left-[11px] bg-amber' : 'left-[1px] bg-dim'
        }`}
      />
    </span>
  )
}

/* ─── Rename panel — inline, expanded under the "Rename all" row ─
   Four naming schemes as small selectable rows; "my word" reveals a
   text input (picker-style). Each change dry-runs a preview and shows
   up to 3 from→to lines with the total. An amber Rename applies it. */

const RENAME_FORMATS: {
  fmt: RenameFmt
  label: string
  example: string
}[] = [
  { fmt: 'date_number', label: 'date + number', example: '2025-08-07_01.jpg' },
  { fmt: 'datetime', label: 'date taken', example: '2025-08-07_143052.jpg' },
  { fmt: 'number', label: 'numbers', example: '001.jpg' },
  { fmt: 'custom', label: 'my word', example: 'word_001.jpg' },
]

interface RenamePanelProps {
  busy: boolean
  working: boolean
  onApply: (fmt: RenameFmt, word: string) => void
}

function RenamePanel({ busy, working, onApply }: RenamePanelProps) {
  const [fmt, setFmt] = useState<RenameFmt>('date_number')
  const [word, setWord] = useState('')
  const [preview, setPreview] = useState<{
    total: number
    examples: { from: string; to: string }[]
  } | null>(null)
  const [previewError, setPreviewError] = useState<string | null>(null)

  const needsWord = fmt === 'custom'
  const wordReady = !needsWord || word.trim().length > 0
  const canApply = wordReady && !working

  // Dry-run a preview on any format/word change (debounced for custom typing).
  // All state writes happen inside the timeout — never synchronously in the
  // effect body — so an empty custom word simply clears the preview deferred.
  useEffect(() => {
    let live = true
    const handle = window.setTimeout(() => {
      if (!wordReady) {
        setPreview(null)
        setPreviewError(null)
        return
      }
      api
        .renamePreview(fmt, needsWord ? word : undefined)
        .then((res) => {
          if (!live) return
          setPreview(res)
          setPreviewError(null)
        })
        .catch((e) => {
          if (!live) return
          setPreview(null)
          setPreviewError(e instanceof ApiError ? e.message : 'preview failed')
        })
    }, needsWord ? 200 : 0)
    return () => {
      live = false
      window.clearTimeout(handle)
    }
  }, [fmt, word, needsWord, wordReady])

  return (
    <div className="fade-in border-b border-hairline bg-panel px-3 py-4">
      {/* Format choices — small selectable rows. */}
      <div className="flex flex-col gap-1.5">
        {RENAME_FORMATS.map((f) => {
          const selected = f.fmt === fmt
          return (
            <button
              key={f.fmt}
              onClick={() => setFmt(f.fmt)}
              className={`flex items-baseline justify-between gap-3 border px-2.5 py-1.5 text-left transition-colors ${
                selected
                  ? 'border-amber-ring bg-amber-wash'
                  : 'border-hairline hover:border-amber-ring'
              }`}
            >
              <span
                className={`font-sans text-[12.5px] ${
                  selected ? 'text-amber' : 'text-text'
                }`}
              >
                {f.label}
              </span>
              <span className="truncate font-mono text-[10.5px] text-dim">
                {f.example}
              </span>
            </button>
          )
        })}
      </div>

      {/* "my word" → reveal a picker-style manual input. */}
      {needsWord && (
        <input
          type="text"
          value={word}
          onChange={(e) => setWord(e.target.value)}
          placeholder="your word"
          spellCheck={false}
          autoCapitalize="off"
          autoCorrect="off"
          className="settings-input mt-2.5"
        />
      )}

      {/* Preview — up to 3 from→to lines + the total. */}
      <div className="mt-3 min-h-[16px]">
        {previewError ? (
          <p className="font-mono text-[10.5px] text-amber">{previewError}</p>
        ) : preview ? (
          <>
            {preview.examples.map((ex) => (
              <p
                key={ex.from}
                className="truncate font-mono text-[10.5px] text-faint"
              >
                {ex.from} → {ex.to}
              </p>
            ))}
            <p className="mt-1.5 font-mono text-[10.5px] text-dim">
              renames {preview.total} photo{preview.total === 1 ? '' : 's'}
            </p>
          </>
        ) : needsWord && !wordReady ? (
          <p className="font-mono text-[10.5px] text-faint">
            type a word to preview…
          </p>
        ) : null}
      </div>

      <button
        onClick={() => onApply(fmt, word)}
        disabled={!canApply}
        className="mt-1 border border-amber-ring bg-amber-wash px-3.5 py-1.5 font-sans text-[12px] text-amber transition-colors hover:bg-amber hover:text-ink disabled:cursor-default disabled:opacity-40 disabled:hover:bg-amber-wash disabled:hover:text-amber"
      >
        {busy ? 'Renaming…' : 'Rename'}
      </button>
    </div>
  )
}
