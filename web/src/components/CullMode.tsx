import { useCallback, useEffect, useMemo, useState } from 'react'
import type { Photo, Series } from '../types'
import { api } from '../api'

interface CullModeProps {
  series: Series[]
  photosById: Map<string, Photo>
  onKeep: (id: string, keep: boolean | null) => void
  onClose: () => void
}

export function CullMode({ series, photosById, onKeep, onClose }: CullModeProps) {
  // Only multi-photo bursts are worth culling.
  const bursts = useMemo(
    () => series.filter((s) => s.photo_ids.length > 1),
    [series],
  )

  const [burstIdx, setBurstIdx] = useState(0)
  const [frameIdx, setFrameIdx] = useState(0)

  const burst = bursts[burstIdx]

  // When entering a burst, pre-highlight the suggested keeper frame.
  useEffect(() => {
    if (!burst) return
    const i = burst.photo_ids.indexOf(burst.suggested_keeper_id)
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setFrameIdx(i >= 0 ? i : 0)
  }, [burst])

  const currentId = burst?.photo_ids[frameIdx]
  const currentPhoto = currentId ? photosById.get(currentId) : undefined

  const nextBurst = useCallback(() => {
    setBurstIdx((b) => Math.min(b + 1, bursts.length - 1))
  }, [bursts.length])

  const prevBurst = useCallback(() => {
    setBurstIdx((b) => Math.max(b - 1, 0))
  }, [])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!burst) {
        if (e.key === 'Escape') onClose()
        return
      }
      switch (e.key) {
        case 'Escape':
          onClose()
          break
        case 'ArrowLeft':
          e.preventDefault()
          setFrameIdx((f) => Math.max(0, f - 1))
          break
        case 'ArrowRight':
          e.preventDefault()
          setFrameIdx((f) => Math.min(burst.photo_ids.length - 1, f + 1))
          break
        case 'ArrowDown':
        case 'Enter':
          e.preventDefault()
          nextBurst()
          break
        case 'ArrowUp':
          e.preventDefault()
          prevBurst()
          break
        case 'k':
        case 'K':
          if (currentId) onKeep(currentId, true)
          break
        case 'x':
        case 'X':
          if (currentId) onKeep(currentId, false)
          break
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [burst, currentId, onKeep, onClose, nextBurst, prevBurst])

  if (bursts.length === 0) {
    return (
      <div className="fixed inset-0 z-50 flex flex-col items-center justify-center gap-3 bg-ink fade-in">
        <p className="font-serif text-xl italic text-dim">no bursts to cull</p>
        <p className="font-mono text-xs text-faint">
          there are no multi-frame series in this library
        </p>
        <button
          onClick={onClose}
          className="mt-2 border border-hairline px-4 py-1.5 font-mono text-[11px] text-dim transition-colors hover:text-text"
        >
          esc to close
        </button>
      </div>
    )
  }

  const keep = currentPhoto?.keep

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-ink fade-in">
      {/* Header */}
      <div className="flex shrink-0 items-center justify-between border-b border-hairline px-5 py-3">
        <div className="flex items-baseline gap-3">
          <span className="font-serif text-lg italic text-text">Cull bursts</span>
          <span className="font-mono text-[11px] text-dim">
            burst {burstIdx + 1} / {bursts.length} · frame {frameIdx + 1} /{' '}
            {burst.photo_ids.length}
          </span>
        </div>
        <button
          onClick={onClose}
          className="font-mono text-[11px] text-dim transition-colors hover:text-text"
        >
          esc
        </button>
      </div>

      {/* Big frame */}
      <div className="relative flex min-h-0 flex-1 items-center justify-center p-6">
        {currentId && (
          <img
            key={currentId}
            src={api.thumb(currentId)}
            alt={currentPhoto?.filename ?? ''}
            className="frame-crossfade max-h-full max-w-full object-contain"
            style={{
              opacity: keep === false ? 0.3 : 1,
              filter: keep === false ? 'grayscale(0.6)' : 'none',
              boxShadow:
                keep === true ? '0 0 0 2px var(--color-amber)' : 'none',
            }}
          />
        )}

        {/* Keep/reject state badge */}
        {keep === true && (
          <div className="absolute left-8 top-8 border border-amber bg-amber-wash px-2 py-1 font-mono text-[10px] uppercase tracking-wide text-amber">
            keep
          </div>
        )}
        {keep === false && (
          <div className="absolute left-8 top-8 border border-hairline bg-black/40 px-2 py-1 font-mono text-[10px] uppercase tracking-wide text-dim">
            reject
          </div>
        )}

        {/* Suggested keeper hint */}
        {currentId === burst.suggested_keeper_id && keep == null && (
          <div className="absolute right-8 top-8 border border-amber-ring px-2 py-1 font-mono text-[10px] uppercase tracking-wide text-amber">
            suggested keeper
          </div>
        )}
      </div>

      {/* Metadata line */}
      {currentPhoto && (
        <div className="flex shrink-0 justify-center gap-4 px-5 pb-2 font-mono text-[10px] text-dim">
          <span>{currentPhoto.filename}</span>
          {currentPhoto.captured_at && (
            <span>{currentPhoto.captured_at.slice(0, 19).replace('T', ' ')}</span>
          )}
          {currentPhoto.camera && <span>{currentPhoto.camera}</span>}
          {currentPhoto.sharpness != null && (
            <span>sharp {Math.round(currentPhoto.sharpness)}</span>
          )}
        </div>
      )}

      {/* Filmstrip */}
      <div className="flex shrink-0 justify-center gap-1.5 overflow-x-auto px-5 pb-3 pt-1">
        {burst.photo_ids.map((id, i) => {
          const p = photosById.get(id)
          const active = i === frameIdx
          const isKeeper = id === burst.suggested_keeper_id
          return (
            <button
              key={id}
              onClick={() => setFrameIdx(i)}
              className="relative h-16 w-16 shrink-0 overflow-hidden bg-panel transition-all"
              style={{
                boxShadow: active
                  ? 'inset 0 0 0 2px var(--color-amber)'
                  : isKeeper
                    ? 'inset 0 0 0 1px var(--color-amber-ring)'
                    : 'inset 0 0 0 1px var(--color-hairline)',
                opacity: p?.keep === false ? 0.35 : active ? 1 : 0.7,
              }}
            >
              <img
                src={api.thumb(id)}
                alt=""
                loading="lazy"
                className="h-full w-full object-cover"
              />
              {p?.keep === true && (
                <span className="absolute left-0.5 top-0.5 h-2 w-2 bg-amber" />
              )}
            </button>
          )
        })}
      </div>

      {/* Keyboard hints */}
      <div className="flex shrink-0 items-center justify-center gap-3 border-t border-hairline px-5 py-2.5 font-mono text-[10px] text-faint">
        <Hint k="K" label="keep" />
        <Hint k="X" label="reject" />
        <Hint k="← →" label="frame" />
        <Hint k="↑ ↓ / ⏎" label="burst" />
        <Hint k="esc" label="close" />
      </div>
    </div>
  )
}

function Hint({ k, label }: { k: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className="keycap">{k}</span>
      <span className="text-dim">{label}</span>
    </span>
  )
}
