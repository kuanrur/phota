import { useState } from 'react'
import type { Album } from '../types'

interface AlbumRailProps {
  albums: Album[]
  activeAlbum?: string
  totalCount: number
  onSelectAlbum: (name: string | undefined) => void
  onCreateAlbum: (name: string) => void
  onDeleteAlbum: (name: string) => void
  onDropOnAlbum: (name: string) => void
}

export function AlbumRail({
  albums,
  activeAlbum,
  totalCount,
  onSelectAlbum,
  onCreateAlbum,
  onDeleteAlbum,
  onDropOnAlbum,
}: AlbumRailProps) {
  const [creating, setCreating] = useState(false)
  const [name, setName] = useState('')
  const [dropTarget, setDropTarget] = useState<string | null>(null)

  function submit() {
    const trimmed = name.trim()
    if (trimmed) onCreateAlbum(trimmed)
    setName('')
    setCreating(false)
  }

  return (
    <aside className="flex h-full w-[200px] shrink-0 flex-col border-r border-hairline bg-panel">
      <div className="flex items-center justify-between px-4 pb-2 pt-4">
        <span className="font-serif text-[15px] italic text-text">Albums</span>
        <button
          onClick={() => setCreating((v) => !v)}
          className="font-mono text-[11px] text-dim transition-colors hover:text-amber"
          title="New album"
        >
          + new
        </button>
      </div>

      {creating && (
        <div className="px-3 pb-2">
          <input
            autoFocus
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') submit()
              if (e.key === 'Escape') {
                setCreating(false)
                setName('')
              }
            }}
            onBlur={submit}
            placeholder="album name…"
            className="w-full border border-hairline bg-ink px-2 py-1.5 font-mono text-[11px] text-text placeholder:text-faint"
          />
        </div>
      )}

      <nav className="flex-1 overflow-y-auto pb-4">
        {/* All photos pseudo-item */}
        <button
          onClick={() => onSelectAlbum(undefined)}
          className="flex w-full items-center justify-between border-l-2 px-4 py-2 text-left transition-colors"
          style={{
            borderColor: !activeAlbum ? 'var(--color-amber)' : 'transparent',
            background: !activeAlbum ? 'var(--color-amber-wash)' : 'transparent',
          }}
        >
          <span
            className="text-[13px]"
            style={{ color: !activeAlbum ? 'var(--color-text)' : 'var(--color-dim)' }}
          >
            All photos
          </span>
          <span className="font-mono text-[11px] text-faint">{totalCount}</span>
        </button>

        {albums.map((a) => {
          const active = activeAlbum === a.name
          const isDrop = dropTarget === a.name
          return (
            <div
              key={a.name}
              onDragOver={(e) => {
                e.preventDefault()
                e.dataTransfer.dropEffect = 'copy'
                setDropTarget(a.name)
              }}
              onDragLeave={() => setDropTarget((t) => (t === a.name ? null : t))}
              onDrop={(e) => {
                e.preventDefault()
                setDropTarget(null)
                onDropOnAlbum(a.name)
              }}
              className="group/album relative"
            >
              <button
                onClick={() => onSelectAlbum(a.name)}
                className="flex w-full items-center justify-between border-l-2 px-4 py-2 text-left transition-colors"
                style={{
                  borderColor: active
                    ? 'var(--color-amber)'
                    : isDrop
                      ? 'var(--color-amber-ring)'
                      : 'transparent',
                  background: active
                    ? 'var(--color-amber-wash)'
                    : isDrop
                      ? 'var(--color-elevated)'
                      : 'transparent',
                }}
              >
                <span
                  className="truncate pr-2 text-[13px]"
                  style={{ color: active ? 'var(--color-text)' : 'var(--color-dim)' }}
                >
                  {a.name}
                </span>
                <span className="shrink-0 font-mono text-[11px] text-faint">
                  {a.count}
                </span>
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  if (confirm(`Delete album "${a.name}"? Photos are not deleted.`))
                    onDeleteAlbum(a.name)
                }}
                title="Delete album"
                className="absolute right-1 top-1/2 -translate-y-1/2 bg-panel px-1.5 font-mono text-[12px] text-faint opacity-0 transition-opacity hover:text-text group-hover/album:opacity-100"
              >
                ×
              </button>
            </div>
          )
        })}

        {albums.length === 0 && (
          <p className="px-4 pt-3 font-mono text-[10px] leading-relaxed text-faint">
            drag photos onto a new album to start organizing
          </p>
        )}
      </nav>
    </aside>
  )
}
