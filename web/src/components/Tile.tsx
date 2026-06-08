import { memo } from 'react'
import type { Photo } from '../types'
import { api } from '../api'
import { CheckIcon, RevealIcon } from './icons'

interface TileProps {
  photo: Photo
  index: number
  selected: boolean
  onSelect: (id: string, e: React.MouseEvent) => void
  onKeep: (id: string, keep: boolean | null) => void
  onReveal: (id: string) => void
  onDragStart: (id: string) => void
}

function fmtTime(iso: string | null): string {
  if (!iso) return '—'
  // Show "YYYY-MM-DD HH:MM" without seconds, no timezone juggling.
  const m = iso.match(/(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2})/)
  if (m) return `${m[1]} ${m[2]}`
  return iso.slice(0, 16).replace('T', ' ')
}

function TileImpl({
  photo,
  index,
  selected,
  onSelect,
  onKeep,
  onReveal,
  onDragStart,
}: TileProps) {
  const isKeep = photo.keep === true
  const isReject = photo.keep === false

  // Staggered entrance: cap delay at index*12ms, max ~400ms.
  const delay = Math.min(index * 12, 400)

  return (
    <div
      draggable
      onDragStart={(e) => {
        onDragStart(photo.id)
        e.dataTransfer.effectAllowed = 'copy'
        e.dataTransfer.setData('text/plain', photo.id)
      }}
      onClick={(e) => onSelect(photo.id, e)}
      className="tile-enter group relative aspect-square cursor-pointer select-none bg-panel outline-none"
      style={{ animationDelay: `${delay}ms` }}
      tabIndex={-1}
    >
      {/* Thumbnail */}
      <img
        src={api.thumb(photo.id)}
        alt={photo.filename}
        loading="lazy"
        draggable={false}
        className="h-full w-full object-cover transition-transform duration-200 ease-out group-hover:scale-[1.015]"
        style={{
          opacity: isReject ? 0.3 : 1,
          filter: isReject ? 'grayscale(0.6)' : 'none',
          transition: 'opacity 200ms ease-out, filter 200ms ease-out, transform 200ms ease-out',
        }}
      />

      {/* Hairline / selection ring */}
      <div
        className="pointer-events-none absolute inset-0 transition-shadow duration-150"
        style={{
          boxShadow: selected
            ? 'inset 0 0 0 1.5px var(--color-amber)'
            : 'inset 0 0 0 1px var(--color-hairline)',
        }}
      />

      {/* amber wash when selected */}
      {selected && (
        <div className="pointer-events-none absolute inset-0 bg-amber-wash" />
      )}

      {/* Reject 1px desaturating line overlay */}
      {isReject && (
        <div
          className="pointer-events-none absolute inset-0"
          style={{ boxShadow: 'inset 0 0 0 1px rgba(255,255,255,0.12)' }}
        />
      )}

      {/* KEEP dot, top-left */}
      {isKeep && (
        <div className="pointer-events-none absolute left-1.5 top-1.5 flex h-3.5 w-3.5 items-center justify-center bg-amber text-ink shadow">
          <CheckIcon size={9} />
        </div>
      )}

      {/* Hover-reveal: reveal-in-finder, top-right */}
      <button
        onClick={(e) => {
          e.stopPropagation()
          onReveal(photo.id)
        }}
        title="Reveal in Finder"
        className="absolute right-1.5 top-1.5 flex h-5 w-5 items-center justify-center border border-hairline bg-black/55 text-text opacity-0 transition-opacity duration-150 hover:bg-elevated group-hover:opacity-100"
      >
        <RevealIcon size={12} />
      </button>

      {/* Bottom gradient + metadata + K/X controls, hover-reveal */}
      <div className="pointer-events-none absolute inset-x-0 bottom-0 flex flex-col gap-1.5 bg-gradient-to-t from-black/85 via-black/40 to-transparent px-1.5 pb-1.5 pt-6 opacity-0 transition-opacity duration-150 group-hover:opacity-100">
        <div className="pointer-events-auto flex items-center justify-between">
          <div className="flex gap-1">
            <button
              onClick={(e) => {
                e.stopPropagation()
                onKeep(photo.id, isKeep ? null : true)
              }}
              title="Keep (K)"
              className="keycap transition-colors"
              style={{
                borderColor: isKeep ? 'var(--color-amber)' : undefined,
                color: isKeep ? 'var(--color-amber)' : undefined,
              }}
            >
              K
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation()
                onKeep(photo.id, isReject ? null : false)
              }}
              title="Reject (X)"
              className="keycap transition-colors"
              style={{
                color: isReject ? 'var(--color-dim)' : undefined,
              }}
            >
              X
            </button>
          </div>
        </div>
        <div className="pointer-events-none truncate font-mono text-[10px] leading-tight text-text/90">
          {photo.filename}
        </div>
        <div className="pointer-events-none flex justify-between gap-2 font-mono text-[9px] leading-tight text-dim">
          <span className="truncate">{fmtTime(photo.captured_at)}</span>
          {photo.sharpness != null && (
            <span className="shrink-0">s{Math.round(photo.sharpness)}</span>
          )}
        </div>
      </div>
    </div>
  )
}

export const Tile = memo(TileImpl)
