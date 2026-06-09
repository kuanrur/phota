import { useCallback, useEffect, useState } from 'react'
import { api } from './api'
import type { FinderFolder, Library } from './types'
import { ArrowLeft, FolderIcon } from './components/icons'

/* ─────────────────────────────────────────────────────────────
   phota — minimal Finder-folder controller.

   A tiny utility window with exactly two states:
     A · Picker     — choose a folder (from Finder, or a pasted path)
     B · Controlling — show ONLY which folder is selected
   No photo grid, no thumbnails. Just the selected folder.
   ───────────────────────────────────────────────────────────── */

type Screen = 'picker' | 'folder'

export default function App() {
  const [screen, setScreen] = useState<Screen>('picker')
  const [booting, setBooting] = useState(true)

  // ── State A — picker ───────────────────────────────────────
  const [folders, setFolders] = useState<FinderFolder[]>([])
  const [finderError, setFinderError] = useState<string | null>(null)
  const [scanning, setScanning] = useState(false)
  const [busyPath, setBusyPath] = useState<string | null>(null)
  const [manualPath, setManualPath] = useState('')
  const [pickError, setPickError] = useState<string | null>(null)

  // ── State B — controlling ──────────────────────────────────
  const [library, setLibrary] = useState<Library | null>(null)
  const [dupeGroups, setDupeGroups] = useState<number>(0)

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
  }, [])

  // ── Boot: jump straight to State B if a folder is active ───
  useEffect(() => {
    api
      .library()
      .then(async (lib) => {
        if (lib.folder) {
          setLibrary(lib)
          const dupes = await api.duplicates().catch(() => [])
          setDupeGroups(dupes.length)
          setScreen('folder')
        } else {
          scanFinder()
        }
      })
      .catch(() => scanFinder())
      .finally(() => setBooting(false))
  }, [scanFinder])

  // ── Adopt a folder → State B ───────────────────────────────
  const open = useCallback(
    async (path: string) => {
      if (!path.trim()) return
      setBusyPath(path)
      setPickError(null)
      try {
        await api.openFolder(path)
        await loadFolder()
        setScreen('folder')
      } catch {
        setPickError('could not open that folder')
      } finally {
        setBusyPath(null)
      }
    },
    [loadFolder],
  )

  // ── Back to State A — re-pick regardless of server's last folder ─
  const changeFolder = useCallback(() => {
    setLibrary(null)
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
            busyPath={busyPath}
            manualPath={manualPath}
            pickError={pickError}
            onManualChange={setManualPath}
            onPick={open}
            onRescan={scanFinder}
          />
        ) : (
          <Controller
            library={library}
            dupeGroups={dupeGroups}
            onChangeFolder={changeFolder}
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
  busyPath: string | null
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
  busyPath,
  manualPath,
  pickError,
  onManualChange,
  onPick,
  onRescan,
}: PickerProps) {
  const busy = busyPath !== null
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
                disabled={busy}
                className="mt-4 border border-hairline px-3 py-1.5 font-sans text-[12px] text-text transition-colors hover:border-amber hover:text-amber disabled:opacity-50"
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
                disabled={busy}
                className="mt-4 border border-hairline px-3 py-1.5 font-sans text-[12px] text-text transition-colors hover:border-amber hover:text-amber disabled:opacity-50"
              >
                Rescan
              </button>
            </div>
          ) : (
            <>
              <ul className="flex flex-col gap-2">
                {folders.map((f, i) => {
                  const opening = busyPath === f.path
                  return (
                    <li
                      key={f.path}
                      className="tile-enter"
                      style={{ animationDelay: `${Math.min(i, 10) * 35}ms` }}
                    >
                      <button
                        disabled={busy}
                        onClick={() => onPick(f.path)}
                        className="group flex w-full items-center gap-3 border border-hairline bg-panel px-4 py-3 text-left transition-colors hover:border-amber-ring hover:bg-elevated disabled:cursor-default disabled:opacity-60"
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
                        {opening && (
                          <span className="flex-none font-mono text-[10px] text-amber">
                            opening…
                          </span>
                        )}
                      </button>
                    </li>
                  )
                })}
              </ul>
              <button
                onClick={onRescan}
                disabled={busy}
                className="mt-5 font-mono text-[11px] text-faint transition-colors hover:text-dim disabled:opacity-50"
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
              disabled={busy || !manualPath.trim()}
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

/* ─── State B — Controller (shows ONLY the selected folder) ──── */

interface ControllerProps {
  library: Library | null
  dupeGroups: number
  onChangeFolder: () => void
}

function Controller({ library, dupeGroups, onChangeFolder }: ControllerProps) {
  const folder = library?.folder ?? ''
  const name = folder.replace(/\/+$/, '').split('/').pop() || folder || '—'
  const count = library?.count ?? 0

  return (
    <div className="relative flex h-full flex-col">
      {/* change-folder link, quietly in the corner */}
      <button
        onClick={onChangeFolder}
        className="absolute left-4 top-4 flex items-center gap-1.5 font-mono text-[11px] text-dim transition-colors hover:text-text"
      >
        <ArrowLeft size={12} />
        change folder
      </button>

      <div className="flex flex-1 flex-col items-center justify-center px-8 text-center">
        <div className="scale-in">
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
        </div>
      </div>
    </div>
  )
}
