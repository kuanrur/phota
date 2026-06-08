import { FolderIcon } from './icons'
import type { FinderFolder } from '../types'

/* ─────────────────────────────────────────────────────────────
   Screen 1 — pick a Finder folder to organize.
   A calm, centered picker over the open Finder windows.
   ───────────────────────────────────────────────────────────── */

interface Props {
  folders: FinderFolder[]
  loading: boolean
  busyPath: string | null
  onPick: (path: string) => void
  onReload: () => void
}

export function FolderPicker({
  folders,
  loading,
  busyPath,
  onPick,
  onReload,
}: Props) {
  return (
    <div className="flex h-full items-center justify-center px-6">
      <div className="scale-in w-full max-w-[460px]">
        <h1 className="select-none font-serif text-[34px] italic leading-none text-text">
          phota
        </h1>
        <p className="mt-3 font-sans text-[13px] text-dim">
          pick a folder to organize
        </p>

        <div className="mt-7">
          {loading ? (
            <div className="font-mono text-[12px] text-faint">
              reading Finder…
            </div>
          ) : folders.length === 0 ? (
            <div className="border border-hairline bg-panel px-5 py-6">
              <p className="font-sans text-[13px] leading-relaxed text-dim">
                No Finder windows open. Open a folder of photos in Finder, then
                reload.
              </p>
              <button
                onClick={onReload}
                className="mt-4 border border-hairline px-3 py-1.5 font-sans text-[12px] text-text transition-colors hover:border-amber hover:text-amber"
              >
                Reload
              </button>
            </div>
          ) : (
            <ul className="flex flex-col gap-2">
              {folders.map((f, i) => {
                const busy = busyPath === f.path
                return (
                  <li
                    key={f.path}
                    className="tile-enter"
                    style={{ animationDelay: `${Math.min(i, 10) * 35}ms` }}
                  >
                    <button
                      disabled={busyPath !== null}
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
                      {busy && (
                        <span className="flex-none font-mono text-[10px] text-amber">
                          opening…
                        </span>
                      )}
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
        </div>

        {!loading && folders.length > 0 && (
          <button
            onClick={onReload}
            disabled={busyPath !== null}
            className="mt-5 font-mono text-[11px] text-faint transition-colors hover:text-dim disabled:opacity-50"
          >
            ↻ rescan Finder
          </button>
        )}
      </div>
    </div>
  )
}
