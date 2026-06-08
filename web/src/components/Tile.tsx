import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { api } from '../api'
import type { Photo } from '../types'

/* ─────────────────────────────────────────────────────────────
   A single draggable / selectable photo tile.
   Drag reorders (dnd-kit); a plain click toggles selection.
   ───────────────────────────────────────────────────────────── */

interface Props {
  photo: Photo
  index: number
  selected: boolean
  isDupe: boolean
  onSelect: (e: React.MouseEvent) => void
}

export function Tile({ photo, index, selected, isDupe, onSelect }: Props) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: photo.id })

  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    animationDelay: `${Math.min(index, 24) * 14}ms`,
    zIndex: isDragging ? 50 : undefined,
  }

  // Border priority: drag > selected > dupe > hairline.
  const border = isDragging
    ? 'var(--color-amber)'
    : selected
      ? 'var(--color-amber)'
      : isDupe
        ? 'rgba(217,164,65,0.5)'
        : 'var(--color-hairline)'

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={isDragging ? '' : 'tile-enter'}
    >
      <button
        {...attributes}
        {...listeners}
        onClick={onSelect}
        className="group relative block w-full cursor-grab touch-none select-none overflow-hidden bg-panel outline-none active:cursor-grabbing"
        style={{
          aspectRatio: '1 / 1',
          border: `1px solid ${border}`,
          boxShadow: isDragging
            ? '0 18px 40px rgba(0,0,0,0.6)'
            : selected
              ? '0 0 0 2px var(--color-amber-ring)'
              : 'none',
          transform: isDragging ? 'scale(1.04)' : undefined,
          background: selected ? 'var(--color-amber-wash)' : 'var(--color-panel)',
        }}
      >
        <img
          src={api.thumb(photo.id)}
          alt=""
          loading="lazy"
          draggable={false}
          className="h-full w-full object-cover"
          style={{ opacity: selected ? 0.92 : 1 }}
        />

        {/* order index badge */}
        <span
          className="absolute left-0 top-0 px-1.5 py-0.5 font-mono text-[10px] leading-none text-ink"
          style={{ background: 'var(--color-amber)' }}
        >
          {String(index + 1).padStart(2, '0')}
        </span>

        {/* dupe badge */}
        {isDupe && (
          <span
            className="absolute right-0 top-0 px-1.5 py-0.5 font-mono text-[9px] uppercase leading-none tracking-wide"
            style={{
              background: 'rgba(11,11,12,0.78)',
              color: 'var(--color-amber)',
            }}
          >
            dupe
          </span>
        )}

        {/* selected check */}
        {selected && (
          <span
            className="absolute bottom-1 right-1 flex h-4 w-4 items-center justify-center rounded-full text-ink"
            style={{ background: 'var(--color-amber)' }}
          >
            <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
              <path d="M20 6 9 17l-5-5" />
            </svg>
          </span>
        )}

        {/* filename on hover */}
        <span
          className="pointer-events-none absolute inset-x-0 bottom-0 truncate px-1.5 py-1 font-mono text-[9.5px] text-text opacity-0 transition-opacity group-hover:opacity-100"
          style={{
            background:
              'linear-gradient(to top, rgba(11,11,12,0.92), rgba(11,11,12,0))',
          }}
        >
          {photo.filename}
        </span>
      </button>
    </div>
  )
}
