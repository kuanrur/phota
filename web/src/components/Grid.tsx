import type { Photo } from '../types'
import { Tile } from './Tile'

interface GridProps {
  photos: Photo[]
  loading: boolean
  selection: Set<string>
  onSelect: (id: string, e: React.MouseEvent) => void
  onKeep: (id: string, keep: boolean | null) => void
  onReveal: (id: string) => void
  onDragStart: (id: string) => void
}

export function Grid({
  photos,
  loading,
  selection,
  onSelect,
  onKeep,
  onReveal,
  onDragStart,
}: GridProps) {
  if (loading && photos.length === 0) {
    return (
      <div className="flex h-full items-center justify-center font-mono text-xs text-dim">
        loading…
      </div>
    )
  }

  if (photos.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-center">
        <p className="font-serif text-lg italic text-dim">nothing here</p>
        <p className="font-mono text-xs text-faint">
          no photos match the current filters
        </p>
      </div>
    )
  }

  return (
    <div
      className="grid gap-2.5 p-4"
      style={{
        gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))',
      }}
    >
      {photos.map((p, i) => (
        <Tile
          key={p.id}
          photo={p}
          index={i}
          selected={selection.has(p.id)}
          onSelect={onSelect}
          onKeep={onKeep}
          onReveal={onReveal}
          onDragStart={onDragStart}
        />
      ))}
    </div>
  )
}
