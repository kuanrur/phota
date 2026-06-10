import { useCallback, useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { api, ApiError } from './api'
import type {
  DuplicateGroup,
  FinderFolder,
  IndexStatus,
  Library,
  OrganizeAction,
  RenameFmt,
} from './types'
import { ArrowLeft, FolderIcon } from './components/icons'

/* ─────────────────────────────────────────────────────────────
   phota — minimal Finder-folder controller (Studio grotesk skin).

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

/** Repeats beyond the single keeper in each group — the number "Set aside
 *  duplicates" would move into duplicates/. */
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
    <div className="flex min-h-full justify-center bg-page p-4 sm:py-12">
      <div className="flex h-fit min-h-full w-full max-w-[620px] flex-col overflow-hidden rounded-[14px] border border-hairline-strong bg-ink shadow-[0_1px_0_rgba(255,255,255,0.04)_inset,0_40px_90px_-30px_rgba(0,0,0,0.8)]">
        {booting ? (
          <div className="flex min-h-[320px] flex-1 items-center justify-center font-mono text-[12px] text-faint">
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
            dupeExtras={dupeExtras}
            onChangeFolder={changeFolder}
            onReload={loadFolder}
          />
        )}
      </div>
    </div>
  )
}

/* ─── Shared chrome ──────────────────────────────────────────── */

/** The window's top bar: a quiet back affordance on the left and the
 *  brand wordmark on the right. `onBack` is omitted on the picker. */
function TopBar({ onBack }: { onBack?: () => void }) {
  return (
    <div className="flex h-[46px] flex-none items-center justify-between border-b border-hairline px-6">
      {onBack ? (
        <button
          onClick={onBack}
          className="flex items-center gap-1.5 font-sans text-[12.5px] font-medium text-dim transition-colors hover:text-mute"
        >
          <ArrowLeft size={12} />
          change folder
        </button>
      ) : (
        <span />
      )}
      <span className="font-sans text-[12.5px] font-bold tracking-[0.02em] text-mute">
        phota
      </span>
    </div>
  )
}

/** Tiny uppercase letterspaced dim section label. */
function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <div className="px-6 pt-6 pb-3 font-sans text-[10.5px] font-bold uppercase tracking-[0.16em] text-faint">
      {children}
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
    <>
      <TopBar />
      <div className="scale-in flex flex-1 flex-col px-6 py-10">
        <h1 className="select-none font-display text-[44px] font-extrabold leading-[0.96] tracking-[-0.035em] text-text">
          phota
        </h1>
        <p className="mt-3 font-mono text-[12px] tracking-[-0.01em] text-dim">
          pick a folder to organize
        </p>

        <div className="mt-8">
          {scanning ? (
            <div className="font-mono text-[12px] text-faint">reading Finder…</div>
          ) : permission ? (
            <div className="rounded-[10px] border border-hairline bg-panel px-5 py-5">
              <p className="font-sans text-[13.5px] leading-relaxed text-mute">
                phota needs permission to read your Finder folders. Open{' '}
                <span className="text-text">System Settings</span> →{' '}
                <span className="text-text">Privacy &amp; Security</span> →{' '}
                <span className="text-text">Automation</span> and allow your
                terminal (Terminal/iTerm) to control Finder, then rescan.
              </p>
              <button
                onClick={onRescan}
                className="mt-4 rounded-[10px] border-[1.5px] border-hairline-strong px-3.5 py-2 font-sans text-[13px] font-semibold text-mute transition-colors hover:border-white/20 hover:text-text"
              >
                Rescan
              </button>
            </div>
          ) : folders.length === 0 ? (
            <div className="rounded-[10px] border border-hairline bg-panel px-5 py-5">
              <p className="font-sans text-[13.5px] leading-relaxed text-mute">
                No folder open in Finder. Open one, or paste a path below.
              </p>
              <button
                onClick={onRescan}
                className="mt-4 rounded-[10px] border-[1.5px] border-hairline-strong px-3.5 py-2 font-sans text-[13px] font-semibold text-mute transition-colors hover:border-white/20 hover:text-text"
              >
                Rescan
              </button>
            </div>
          ) : (
            <>
              <div className="mb-3 font-sans text-[10.5px] font-bold uppercase tracking-[0.16em] text-faint">
                open in Finder
              </div>
              <ul className="flex flex-col gap-2">
                {folders.map((f, i) => (
                  <li
                    key={f.path}
                    className="tile-enter"
                    style={{ animationDelay: `${Math.min(i, 10) * 35}ms` }}
                  >
                    <button
                      onClick={() => onPick(f.path)}
                      className="group flex w-full items-center gap-3 rounded-[10px] border border-hairline bg-panel px-4 py-3.5 text-left transition-colors hover:border-amber-ring hover:bg-elevated"
                    >
                      <span className="flex-none text-dim transition-colors group-hover:text-amber">
                        <FolderIcon size={16} />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate font-display text-[15px] font-semibold tracking-[-0.018em] text-text">
                          {f.name}
                        </span>
                        <span className="mt-0.5 block truncate font-mono text-[11px] tracking-[-0.01em] text-dim">
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
        <div className="mt-9 border-t border-hairline pt-6">
          <div className="mb-3 font-sans text-[10.5px] font-bold uppercase tracking-[0.16em] text-faint">
            or paste a path
          </div>
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
              placeholder="/Users/you/Pictures"
              spellCheck={false}
              autoCapitalize="off"
              autoCorrect="off"
              className="settings-input flex-1"
            />
            <button
              type="submit"
              disabled={!manualPath.trim()}
              className="flex-none rounded-[10px] border-[1.5px] border-hairline-strong px-4 py-2 font-sans text-[13px] font-semibold text-mute transition-colors hover:border-white/20 hover:text-text disabled:cursor-default disabled:opacity-40 disabled:hover:border-hairline-strong disabled:hover:text-mute"
            >
              Open
            </button>
          </form>
          {pickError && (
            <p className="mt-2 font-mono text-[11px] text-amber">{pickError}</p>
          )}
        </div>
      </div>
    </>
  )
}

/* ─── Indexing — the chosen folder is being scanned ─────────────
   Folder name in Archivo bold, a hairline track with an amber 2px
   fill (done / total), no spinner, no photos. */

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
    <>
      <TopBar onBack={onBack} />
      <div className="scale-in flex flex-1 flex-col justify-center px-6 py-10">
        <div
          className="truncate font-display text-[44px] font-extrabold leading-[0.96] tracking-[-0.035em] text-text"
          title={name}
        >
          {name}
        </div>
        <div
          className="mt-3.5 truncate font-mono text-[12px] tracking-[-0.01em] text-dim"
          title={folder}
        >
          {folder}
        </div>

        {fatal ? (
          <div className="mt-10">
            <p className="font-mono text-[12px] text-amber">{error}</p>
            <button
              onClick={onBack}
              className="mt-4 rounded-[10px] border-[1.5px] border-hairline-strong px-3.5 py-2 font-sans text-[13px] font-semibold text-mute transition-colors hover:border-white/20 hover:text-text"
            >
              ← back to picker
            </button>
          </div>
        ) : (
          <div className="mt-10">
            {/* Slim hairline track with an amber 2px fill. */}
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

            <p className="mt-3.5 font-mono text-[12px] tracking-[-0.01em] text-dim">
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
    </>
  )
}

/* ─── State B — Controller (shows ONLY the selected folder) ──── */

interface ControllerProps {
  library: Library | null
  dupeExtras: number
  onChangeFolder: () => void
  onReload: () => Promise<void>
}

type Action = OrganizeAction
type Busy = Action | 'undo' | 'rename' | 'tidy' | 'keep' | null

function Controller({
  library,
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

  // ── Rename panel — expanded inline under the "Rename photos" row ─
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
    async (fmt: RenameFmt, word: string, formats: string[] | undefined) => {
      setBusy('rename')
      setStatus(null)
      try {
        const { renamed } = await api.renameApply(
          fmt,
          fmt === 'custom' ? word : undefined,
          formats,
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

  // Repeats shown in the meta line and the Clean up row count.
  const repeats = dupeExtras

  return (
    <div className="flex flex-1 flex-col overflow-y-auto">
      <TopBar onBack={onChangeFolder} />

      <div className="scale-in flex flex-1 flex-col">
        {/* ── Folder block ──────────────────────────────────── */}
        <div className="px-6 pt-8 pb-6">
          <div
            className="truncate font-display text-[54px] font-extrabold leading-[0.96] tracking-[-0.035em] text-text"
            title={name}
          >
            {name}
          </div>
          <div
            className="mt-3.5 truncate font-mono text-[12px] tracking-[-0.01em] text-dim"
            title={folder}
          >
            {folder}
          </div>
          <div className="mt-1.5 font-mono text-[12px] tracking-[-0.01em] text-faint">
            <span className="text-mute">
              {count} photo{count === 1 ? '' : 's'}
            </span>
            {repeats > 0 && (
              <>
                {' · '}
                {repeats} repeat{repeats === 1 ? '' : 's'}
              </>
            )}
          </div>
        </div>

        {/* ── RENAME ────────────────────────────────────────── */}
        <SectionLabel>Rename</SectionLabel>
        <button
          onClick={() => setRenameOpen((v) => !v)}
          disabled={working}
          aria-expanded={renameOpen}
          className={`group flex w-full items-center gap-4 border-t border-hairline px-6 py-6 text-left transition-colors hover:bg-white/[0.018] disabled:cursor-default disabled:hover:bg-transparent ${
            renameOpen ? 'bg-white/[0.022]' : ''
          }`}
        >
          <span className="min-w-0 flex-1">
            <span className="block font-display text-[18px] font-semibold leading-tight tracking-[-0.018em] text-text">
              Rename photos
            </span>
            <span className="mt-1.5 block font-sans text-[13px] leading-snug tracking-[-0.005em] text-dim">
              date, numbers, or your own word
            </span>
          </span>
          <Chevron open={renameOpen} />
        </button>
        {renameOpen && (
          <RenamePanel
            busy={busy === 'rename'}
            working={working}
            count={count}
            formats={library?.formats ?? {}}
            onApply={applyRename}
          />
        )}

        {/* ── PUT IN ORDER ──────────────────────────────────── */}
        <SectionLabel>Put in order</SectionLabel>
        <Row
          title="Number by date"
          disabled={working}
          onClick={() => run('sort_by_date')}
          count={count}
          sub={
            <>
              renames oldest → newest (
              <code className="font-mono text-[11.5px]">001_, 002_…</code>)
            </>
          }
        />

        {/* ── MAKE FOLDERS ──────────────────────────────────── */}
        <SectionLabel>Make folders</SectionLabel>
        <Row
          title="By day"
          disabled={working}
          onClick={() => run('by_day')}
          count={count}
          sub={
            <>
              moves photos into{' '}
              <code className="font-mono text-[11.5px]">2025-08-07/</code>
            </>
          }
        />
        <Row
          title="By camera"
          disabled={working}
          onClick={() => run('by_camera')}
          count={count}
          sub={
            <>
              moves photos into{' '}
              <code className="font-mono text-[11.5px]">iPhone 15/, X-T5/</code>
            </>
          }
        />
        <Row
          title="By file type"
          disabled={working}
          onClick={() => run('by_format')}
          count={count}
          sub={
            <>
              moves photos into{' '}
              <code className="font-mono text-[11.5px]">JPEG/, PNG/</code>
            </>
          }
        />

        {/* ── CLEAN UP ──────────────────────────────────────── */}
        <SectionLabel>Clean up</SectionLabel>
        <Row
          title="Set aside duplicates"
          disabled={working || dupeExtras === 0}
          empty={dupeExtras === 0}
          onClick={() => run('duplicates')}
          count={dupeExtras}
          sub={
            <>
              moves repeats into{' '}
              <code className="font-mono text-[11.5px]">duplicates/</code>, keeps
              the sharpest
            </>
          }
        />

        {/* ── FINDER ────────────────────────────────────────── */}
        <SectionLabel>Finder</SectionLabel>
        <Row
          title="Tidy icons"
          disabled={working}
          onClick={tidyIcons}
          sub="snap Finder icons to an even grid"
        />
        <button
          onClick={toggleKeep}
          disabled={working}
          role="switch"
          aria-checked={arranged}
          className="group flex w-full items-center gap-4 border-t border-hairline px-6 py-6 text-left transition-colors hover:bg-white/[0.018] disabled:cursor-default disabled:hover:bg-transparent"
        >
          <span className="min-w-0 flex-1">
            <span className="block font-display text-[18px] font-semibold leading-tight tracking-[-0.018em] text-text">
              Keep tidy
            </span>
            <span className="mt-1.5 block font-sans text-[13px] leading-snug tracking-[-0.005em] text-dim">
              keep this folder auto-arranged
            </span>
          </span>
          <span className="flex-none">
            <Toggle on={arranged} />
          </span>
        </button>

        {/* ── FOOTER ────────────────────────────────────────── */}
        <div className="mt-auto flex items-center gap-4 border-t border-hairline-strong px-6 py-6">
          <button
            onClick={undo}
            disabled={working}
            className="flex-none rounded-[10px] border-[1.5px] border-hairline-strong px-4 py-2 font-sans text-[13.5px] font-semibold text-mute transition-colors hover:border-white/[0.22] hover:text-text disabled:cursor-default disabled:opacity-40 disabled:hover:border-hairline-strong disabled:hover:text-mute"
          >
            Undo last change
          </button>

          <div className="min-w-0 flex-1">
            {working ? (
              <span className="font-mono text-[12px] tracking-[-0.01em] text-amber">
                Working…
              </span>
            ) : status ? (
              <span
                className={`font-mono text-[12px] tracking-[-0.01em] ${
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
  )
}

/* ─── A single tappable action row (full-width hairline + count) ── */

interface RowProps {
  title: string
  sub: ReactNode
  onClick: () => void
  disabled?: boolean
  /** Affected count, shown in quiet amber mono on the right. */
  count?: number
  /** When true, render the disabled "none found" state instead of a count. */
  empty?: boolean
}

function Row({ title, sub, onClick, disabled, count, empty }: RowProps) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="group flex w-full items-center gap-4 border-t border-hairline px-6 py-6 text-left transition-colors hover:bg-white/[0.018] disabled:cursor-default disabled:hover:bg-transparent"
    >
      <span className="min-w-0 flex-1">
        <span className="block font-display text-[18px] font-semibold leading-tight tracking-[-0.018em] text-text group-disabled:text-dim">
          {title}
        </span>
        <span className="mt-1.5 block font-sans text-[13px] leading-snug tracking-[-0.005em] text-dim">
          {sub}
        </span>
      </span>
      {empty ? (
        <span className="flex-none font-mono text-[12px] tracking-[-0.01em] text-faint">
          none found
        </span>
      ) : count !== undefined ? (
        <span className="flex-none font-mono text-[12px] tracking-[-0.01em] text-amber/80">
          {count}
        </span>
      ) : null}
      <Chevron />
    </button>
  )
}

/* ─── Chevron — rotates + turns amber when its row is expanded. ── */

function Chevron({ open = false }: { open?: boolean }) {
  return (
    <span
      className={`w-[14px] flex-none text-center text-[13px] transition-all ${
        open ? 'rotate-90 text-amber' : 'text-faint'
      }`}
    >
      ›
    </span>
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

/* ─── Finder · amber pill toggle ─────────────────────────────────
   A hairline pill that fills amber when on; the knob slides + darkens. */

function Toggle({ on }: { on: boolean }) {
  return (
    <span
      className={`relative block h-[24px] w-[42px] rounded-full border transition-colors ${
        on ? 'border-amber bg-amber' : 'border-hairline-strong bg-elevated'
      }`}
    >
      <span
        className={`absolute top-[2px] h-[18px] w-[18px] rounded-full transition-all ${
          on
            ? 'left-[22px] bg-amber-ink'
            : 'left-[2px] bg-dim'
        }`}
      />
    </span>
  )
}

/* ─── Rename panel — inline, expanded under the "Rename photos" row ─
   include-format chips, four naming-scheme chips ("your word" reveals a
   text input), a live preview of up to 3 from→to lines + the total, and
   a solid-amber apply button. */

const RENAME_FORMATS: {
  fmt: RenameFmt
  label: string
  example: string
}[] = [
  { fmt: 'date_number', label: 'date + number', example: '2025-08-07_01.jpg' },
  { fmt: 'datetime', label: 'date & time', example: '2025-08-07_143052.jpg' },
  { fmt: 'number', label: 'numbers', example: '001.jpg' },
]

interface RenamePanelProps {
  busy: boolean
  working: boolean
  /** Total photos in the active folder — for the primary button label. */
  count: number
  /** Photo count per file-type label (e.g. { JPEG: 5, PNG: 2 }). */
  formats: Record<string, number>
  onApply: (
    fmt: RenameFmt,
    word: string,
    formats: string[] | undefined,
  ) => void
}

function RenamePanel({ busy, working, count, formats, onApply }: RenamePanelProps) {
  const [fmt, setFmt] = useState<RenameFmt>('date_number')
  const [word, setWord] = useState('')
  const [preview, setPreview] = useState<{
    total: number
    examples: { from: string; to: string }[]
  } | null>(null)
  const [previewError, setPreviewError] = useState<string | null>(null)

  // ── Scope — which file types to include (all selected by default) ──
  const allLabels = Object.keys(formats)
  // Set of *excluded* labels; absence means "included", so a freshly-loaded
  // folder (and any newly-discovered type) starts fully selected.
  const [excluded, setExcluded] = useState<Set<string>>(new Set())
  const selected = allLabels.filter((l) => !excluded.has(l))
  const allSelected = selected.length === allLabels.length
  const noneSelected = allLabels.length > 0 && selected.length === 0
  // Omit the param entirely when every type is selected (server treats
  // omitted = all); otherwise send the explicit selection.
  const scopeKey = allSelected ? '*' : [...selected].sort().join(',')
  const scopeFormats = allSelected ? undefined : selected

  const toggleLabel = useCallback((label: string) => {
    setExcluded((prev) => {
      const next = new Set(prev)
      if (next.has(label)) next.delete(label)
      else next.add(label)
      return next
    })
  }, [])

  const needsWord = fmt === 'custom'
  const wordReady = !needsWord || word.trim().length > 0
  const canApply = wordReady && !working && !noneSelected

  // The primary button affects the previewed total when known, else the
  // folder count (mirrors the "renames N photos" countline below).
  const affected = preview?.total ?? count

  // Dry-run a preview on any format/word/scope change (debounced for custom
  // typing). All state writes happen inside the timeout — never synchronously
  // in the effect body — so an empty custom word (or empty scope) simply
  // clears the preview deferred.
  useEffect(() => {
    let live = true
    const handle = window.setTimeout(() => {
      if (!wordReady || noneSelected) {
        setPreview(null)
        setPreviewError(null)
        return
      }
      api
        .renamePreview(fmt, needsWord ? word : undefined, scopeFormats)
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
    // `scopeKey` captures the selection; `scopeFormats` is derived from it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fmt, word, needsWord, wordReady, scopeKey, noneSelected])

  return (
    <div className="fade-in border-t border-hairline bg-black/[0.22] px-6 pt-6 pb-8">
      {/* include — only the chosen file types (all on by default). */}
      {allLabels.length > 0 && (
        <div className="mb-6">
          <div className="mb-3 font-sans text-[10.5px] font-bold uppercase tracking-[0.14em] text-faint">
            include
          </div>
          <div className="flex flex-wrap gap-2">
            {allLabels.map((label) => {
              const on = !excluded.has(label)
              return (
                <button
                  key={label}
                  onClick={() => toggleLabel(label)}
                  aria-pressed={on}
                  className={`inline-flex h-[34px] items-center gap-2 rounded-full border-[1.5px] px-3.5 font-sans text-[13px] font-semibold tracking-[-0.005em] transition-colors ${
                    on
                      ? 'border-amber bg-amber-wash text-text'
                      : 'border-dashed border-hairline-strong text-mute opacity-50 hover:border-white/20'
                  }`}
                >
                  {label}{' '}
                  <span
                    className={`font-mono text-[11px] font-normal ${
                      on ? 'text-amber' : 'text-faint'
                    }`}
                  >
                    {formats[label]}
                  </span>
                </button>
              )
            })}
          </div>
        </div>
      )}

      {/* name them — naming-scheme chips ("your word" reveals an input). */}
      <div className="mb-1">
        <div className="mb-3 font-sans text-[10.5px] font-bold uppercase tracking-[0.14em] text-faint">
          name them
        </div>
        <div className="flex flex-wrap gap-2">
          {RENAME_FORMATS.map((f) => {
            const sel = f.fmt === fmt
            return (
              <button
                key={f.fmt}
                onClick={() => setFmt(f.fmt)}
                className={`flex flex-col items-start gap-[3px] rounded-[12px] border-[1.5px] px-3.5 py-[9px] text-left transition-colors ${
                  sel
                    ? 'border-amber bg-amber-wash'
                    : 'border-hairline-strong hover:border-white/20'
                }`}
              >
                <span
                  className={`font-sans text-[13px] font-semibold ${
                    sel ? 'text-text' : 'text-mute'
                  }`}
                >
                  {f.label}
                </span>
                <span
                  className={`font-mono text-[10.5px] tracking-[-0.01em] ${
                    sel ? 'text-amber' : 'text-faint'
                  }`}
                >
                  {f.example}
                </span>
              </button>
            )
          })}

          {/* your word — a chip with a revealed monospace input. */}
          <div
            className={`flex flex-col items-start gap-1.5 rounded-[12px] border-[1.5px] px-3 pt-[9px] pb-[11px] transition-colors ${
              needsWord
                ? 'border-amber bg-amber-wash'
                : 'border-hairline-strong'
            }`}
          >
            <button
              onClick={() => setFmt('custom')}
              className={`font-sans text-[13px] font-semibold ${
                needsWord ? 'text-text' : 'text-mute'
              }`}
            >
              your word
            </button>
            <input
              type="text"
              value={word}
              onFocusCapture={() => setFmt('custom')}
              onChange={(e) => {
                setFmt('custom')
                setWord(e.target.value)
              }}
              placeholder="tokyo or 🌊"
              spellCheck={false}
              autoCapitalize="off"
              autoCorrect="off"
              className="h-[30px] w-[108px] rounded-lg border-[1.5px] border-amber-ring bg-black/30 px-2.5 font-mono text-[15px] text-text outline-none placeholder:text-faint"
            />
          </div>
        </div>
      </div>

      {/* Preview — up to 3 from→to lines + the total. */}
      <div className="mt-6 rounded-[10px] border border-hairline bg-black/30 p-4">
        {noneSelected ? (
          <p className="font-mono text-[12.5px] leading-[1.85] text-faint">
            select at least one type
          </p>
        ) : previewError ? (
          <p className="font-mono text-[12.5px] leading-[1.85] text-amber">
            {previewError}
          </p>
        ) : preview ? (
          <>
            {preview.examples.map((ex) => (
              <p
                key={ex.from}
                className="truncate font-mono text-[12.5px] leading-[1.85] tracking-[-0.02em] text-dim"
              >
                {ex.from} <span className="px-2 text-faint">→</span>{' '}
                <span className="text-amber">{ex.to}</span>
              </p>
            ))}
            <p className="font-mono text-[12.5px] leading-[1.85] text-faint">…</p>
          </>
        ) : needsWord && !wordReady ? (
          <p className="font-mono text-[12.5px] leading-[1.85] text-faint">
            type a word to preview…
          </p>
        ) : (
          <p className="font-mono text-[12.5px] leading-[1.85] text-faint">…</p>
        )}
      </div>

      {/* Action — countline + solid-amber apply button. */}
      <div className="mt-6 flex items-center justify-between gap-4">
        <span className="font-mono text-[12px] tracking-[-0.01em] text-dim">
          {noneSelected
            ? 'select at least one type'
            : `renames ${affected} photo${affected === 1 ? '' : 's'}`}
        </span>
        <button
          onClick={() => onApply(fmt, word, scopeFormats)}
          disabled={!canApply}
          className="h-[40px] flex-none rounded-[10px] bg-amber px-5 font-sans text-[14px] font-bold tracking-[-0.01em] text-amber-ink transition-[filter] hover:brightness-[1.07] disabled:cursor-default disabled:opacity-40 disabled:hover:brightness-100"
        >
          {busy
            ? 'Renaming…'
            : `Rename ${affected} photo${affected === 1 ? '' : 's'}`}
        </button>
      </div>
    </div>
  )
}
