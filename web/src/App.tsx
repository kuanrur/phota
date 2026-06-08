import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api } from './api'
import type { AiStatus, Library, Photo } from './types'
import { Settings } from './components/Settings'
import { GearIcon, RevealIcon, CheckIcon } from './components/icons'

/* ─────────────────────────────────────────────────────────────
   phota — command bar
   A slim, search-led palette (Spotlight / Raycast feel).
   The photos open in Finder / Preview, never inside the window.
   ───────────────────────────────────────────────────────────── */

export default function App() {
  const [library, setLibrary] = useState<Library | null>(null)
  const [aiStatus, setAiStatus] = useState<AiStatus | null>(null)
  const [photos, setPhotos] = useState<Photo[]>([])

  const [query, setQuery] = useState('')
  // Semantic-search ids (AI), ordered best-first. null = none/cleared.
  const [searchIds, setSearchIds] = useState<string[] | null>(null)

  // The user's explicit pick. The *effective* selection is derived below so it
  // always falls back to the first result without a reconciling effect.
  const [pickedId, setPickedId] = useState<string | null>(null)
  const [settingsOpen, setSettingsOpen] = useState(false)

  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLDivElement>(null)
  const rowRefs = useRef<Map<string, HTMLDivElement>>(new Map())

  // ── Initial loads ──────────────────────────────────────────
  useEffect(() => {
    api.library().then(setLibrary).catch(() => setLibrary(null))
    api.photos().then(setPhotos).catch(() => setPhotos([]))
    api.getAiSettings().then(setAiStatus).catch(() => setAiStatus(null))
  }, [])

  // ── Series sizes (group loaded photos by series_id) ────────
  const seriesSizes = useMemo(() => {
    const m = new Map<number, number>()
    for (const p of photos) {
      if (p.series_id != null) m.set(p.series_id, (m.get(p.series_id) ?? 0) + 1)
    }
    return m
  }, [photos])

  // Photos come captured_at-ascending; newest-first is the resting order.
  const newestFirst = useMemo(() => [...photos].reverse(), [photos])

  // ── Debounced semantic search (AI on + query >= 2 chars) ───
  // We only fire the request when eligible; `searchIds` is otherwise ignored by
  // the `results` derivation, so there is no need to clear it synchronously.
  const aiEligible = aiStatus?.configured === true && query.trim().length >= 2

  useEffect(() => {
    if (!aiEligible) return
    const q = query.trim()
    let cancelled = false
    const t = setTimeout(() => {
      api
        .search(q)
        .then((ids) => {
          if (!cancelled) setSearchIds(ids)
        })
        .catch(() => {
          // 409 (AI not configured) or any failure → silent fallback to text.
          if (!cancelled) setSearchIds(null)
        })
    }, 250)
    return () => {
      cancelled = true
      clearTimeout(t)
    }
  }, [query, aiEligible])

  // ── Derived results ────────────────────────────────────────
  const results = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return newestFirst

    const matches = (p: Photo) =>
      p.filename.toLowerCase().includes(q) ||
      (p.camera?.toLowerCase().includes(q) ?? false) ||
      (p.captured_at?.toLowerCase().includes(q) ?? false)

    const textMatches = newestFirst.filter(matches)

    if (aiEligible && searchIds && searchIds.length) {
      // Semantic matches rank FIRST (in API order), then text matches that
      // weren't already covered semantically.
      const byId = new Map(photos.map((p) => [p.id, p]))
      const seen = new Set<string>()
      const out: Photo[] = []
      for (const id of searchIds) {
        const p = byId.get(id)
        if (p && !seen.has(id)) {
          out.push(p)
          seen.add(id)
        }
      }
      for (const p of textMatches) {
        if (!seen.has(p.id)) {
          out.push(p)
          seen.add(p.id)
        }
      }
      return out
    }

    return textMatches
  }, [query, newestFirst, searchIds, photos, aiEligible])

  // ── Effective selection (derived — no reconciling effect) ──
  // Honour the user's pick when it's still in the result set, otherwise fall
  // back to the first row. Typing/filtering therefore "resets to first" for
  // free, and an empty result set yields null.
  const selectedId = useMemo(() => {
    if (results.length === 0) return null
    if (pickedId && results.some((p) => p.id === pickedId)) return pickedId
    return results[0].id
  }, [results, pickedId])

  const selectedIndex = useMemo(
    () => results.findIndex((p) => p.id === selectedId),
    [results, selectedId],
  )

  const scrollIntoView = useCallback((id: string) => {
    const el = rowRefs.current.get(id)
    el?.scrollIntoView({ block: 'nearest' })
  }, [])

  const move = useCallback(
    (delta: number) => {
      if (results.length === 0) return
      const cur = selectedIndex < 0 ? 0 : selectedIndex
      const next = Math.min(results.length - 1, Math.max(0, cur + delta))
      const id = results[next].id
      setPickedId(id)
      scrollIntoView(id)
    },
    [results, selectedIndex, scrollIntoView],
  )

  // ── Optimistic keep / reject ───────────────────────────────
  const applyKeep = useCallback((id: string, keep: boolean | null) => {
    setPhotos((prev) => prev.map((p) => (p.id === id ? { ...p, keep } : p)))
    api.setKeep(id, keep).catch(() => {
      // On failure, re-pull truth for this library.
      api.photos().then(setPhotos).catch(() => {})
    })
  }, [])

  const doReveal = useCallback((id: string) => {
    api.reveal(id).catch(() => {})
  }, [])
  const doOpen = useCallback((id: string) => {
    api.openFile(id).catch(() => {})
  }, [])

  // ── Window-level keyboard handling ─────────────────────────
  // The search box stays focused the whole time and captures letters, so the
  // action keys are bound on the meta/ctrl modifier to avoid clobbering text.
  //   ↵            reveal selected in Finder
  //   ↑ / ↓        move selection
  //   ⌘K / ⌃K      keep selected
  //   ⌘X / ⌃X      reject selected
  //   ⌘O / ⌃O      open selected in Preview
  //   esc          clear query (then blur)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (settingsOpen) return
      const mod = e.metaKey || e.ctrlKey

      if (e.key === 'ArrowDown') {
        e.preventDefault()
        move(1)
        return
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault()
        move(-1)
        return
      }
      if (e.key === 'Enter') {
        if (selectedId) {
          e.preventDefault()
          doReveal(selectedId)
        }
        return
      }
      if (e.key === 'Escape') {
        e.preventDefault()
        if (query) setQuery('')
        else inputRef.current?.blur()
        return
      }
      if (mod && (e.key === 'k' || e.key === 'K')) {
        if (selectedId) {
          e.preventDefault()
          applyKeep(selectedId, true)
        }
        return
      }
      if (mod && (e.key === 'x' || e.key === 'X')) {
        if (selectedId) {
          e.preventDefault()
          applyKeep(selectedId, false)
        }
        return
      }
      if (mod && (e.key === 'o' || e.key === 'O')) {
        if (selectedId) {
          e.preventDefault()
          doOpen(selectedId)
        }
        return
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [settingsOpen, query, selectedId, move, doReveal, doOpen, applyKeep])

  const aiOn = aiStatus?.configured === true

  return (
    <div className="flex h-full justify-center bg-ink p-2">
      <div className="flex h-full w-full max-w-[720px] flex-col overflow-hidden rounded-[10px] border border-hairline bg-ink shadow-2xl">
        {/* ── Search row ─────────────────────────────────────── */}
        <div className="flex items-center gap-3 border-b border-hairline px-5 py-3.5">
          <input
            ref={inputRef}
            autoFocus
            value={query}
            onChange={(e) => {
              setQuery(e.target.value)
              // Typing resets selection to the first row: clearing the explicit
              // pick lets the derived selection fall back to results[0].
              setPickedId(null)
            }}
            placeholder="search your photos…"
            spellCheck={false}
            autoComplete="off"
            className="min-w-0 flex-1 bg-transparent text-[19px] font-light text-text placeholder:text-faint focus:outline-none"
            style={{ fontFamily: 'var(--font-sans)' }}
          />

          <span className="select-none font-serif text-[13px] italic text-faint">
            phota
          </span>

          <span
            className="select-none border px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wide"
            style={{
              color: aiOn ? 'var(--color-amber)' : 'var(--color-dim)',
              borderColor: aiOn
                ? 'var(--color-amber-ring)'
                : 'var(--color-hairline)',
              background: aiOn ? 'var(--color-amber-wash)' : 'transparent',
            }}
            title={
              aiOn ? 'AI search enabled' : 'AI not configured — open settings'
            }
          >
            AI
          </span>

          <button
            onClick={() => setSettingsOpen(true)}
            className="text-dim transition-colors hover:text-text"
            aria-label="Settings"
            title="Settings"
          >
            <GearIcon size={15} />
          </button>
        </div>

        {/* ── Results list ───────────────────────────────────── */}
        <div ref={listRef} className="min-h-0 flex-1 overflow-y-auto">
          {results.length === 0 ? (
            <div className="flex h-full items-center justify-center font-mono text-[12px] text-faint">
              {photos.length === 0 ? 'loading…' : 'no matches'}
            </div>
          ) : (
            results.map((p, i) => (
              <Row
                key={p.id}
                photo={p}
                selected={p.id === selectedId}
                seriesSize={p.series_id != null ? seriesSizes.get(p.series_id) ?? 1 : 1}
                onSelect={() => setPickedId(p.id)}
                onReveal={() => doReveal(p.id)}
                onOpen={() => doOpen(p.id)}
                onKeep={() => applyKeep(p.id, p.keep === true ? null : true)}
                onReject={() => applyKeep(p.id, p.keep === false ? null : false)}
                registerRef={(el) => {
                  if (el) rowRefs.current.set(p.id, el)
                  else rowRefs.current.delete(p.id)
                }}
                index={i}
              />
            ))
          )}
        </div>

        {/* ── Footer hint bar ────────────────────────────────── */}
        <div className="flex items-center gap-4 border-t border-hairline px-5 py-2 font-mono text-[10px] text-faint">
          <span>
            <kbd className="text-dim">↵</kbd> reveal
          </span>
          <span>
            <kbd className="text-dim">⌘O</kbd> open
          </span>
          <span>
            <kbd className="text-dim">⌘K</kbd> keep
          </span>
          <span>
            <kbd className="text-dim">⌘X</kbd> reject
          </span>
          <span>
            <kbd className="text-dim">↑↓</kbd> move
          </span>
          <span>
            <kbd className="text-dim">esc</kbd> clear
          </span>
          <span className="ml-auto text-faint">
            {library?.count != null ? `${results.length}/${library.count}` : ''}
          </span>
        </div>
      </div>

      {settingsOpen && (
        <Settings
          status={aiStatus}
          onClose={() => setSettingsOpen(false)}
          onSaved={setAiStatus}
        />
      )}
    </div>
  )
}

// ── Result row ───────────────────────────────────────────────

interface RowProps {
  photo: Photo
  selected: boolean
  seriesSize: number
  index: number
  onSelect: () => void
  onReveal: () => void
  onOpen: () => void
  onKeep: () => void
  onReject: () => void
  registerRef: (el: HTMLDivElement | null) => void
}

function Row({
  photo,
  selected,
  seriesSize,
  index,
  onSelect,
  onReveal,
  onOpen,
  onKeep,
  onReject,
  registerRef,
}: RowProps) {
  const rejected = photo.keep === false
  const kept = photo.keep === true
  const date = photo.captured_at ? photo.captured_at.slice(0, 10) : '—'
  const sub = `${date} · ${photo.camera ?? 'unknown'}`

  // Stop arrow buttons from also triggering the row's onClick selection
  // double-firing is harmless but keep clicks scoped.
  const stop = (fn: () => void) => (e: React.MouseEvent) => {
    e.stopPropagation()
    fn()
  }

  return (
    <div
      ref={registerRef}
      onClick={onSelect}
      className="tile-enter group flex cursor-default items-center gap-3 border-l-2 px-5 py-2"
      style={{
        animationDelay: `${Math.min(index, 12) * 18}ms`,
        borderLeftColor: selected ? 'var(--color-amber)' : 'transparent',
        background: selected ? 'rgba(255,255,255,0.05)' : 'transparent',
        opacity: rejected ? 0.45 : 1,
      }}
    >
      <img
        src={api.thumb(photo.id)}
        alt=""
        loading="lazy"
        className="h-10 w-10 flex-none border border-hairline object-cover"
        style={{ background: 'var(--color-panel)' }}
      />

      <div className="min-w-0 flex-1">
        <div className="truncate font-mono text-[12.5px] text-text">
          {photo.filename}
        </div>
        <div className="flex items-center gap-2 font-mono text-[10.5px] text-dim">
          <span className="truncate">{sub}</span>
          {seriesSize > 1 && (
            <span className="flex-none border border-hairline px-1 py-px text-[9px] text-faint">
              burst of {seriesSize}
            </span>
          )}
        </div>
      </div>

      {/* On-row action buttons — shown on hover or when selected. */}
      <div
        className="flex flex-none items-center gap-1 transition-opacity"
        style={{ opacity: selected ? 1 : undefined }}
      >
        <RowButton title="Reveal in Finder" onClick={stop(onReveal)}>
          <RevealIcon size={13} />
        </RowButton>
        <RowButton title="Open in Preview" onClick={stop(onOpen)}>
          <OpenGlyph />
        </RowButton>
        <RowButton title="Keep" onClick={stop(onKeep)} active={kept}>
          <CheckIcon size={12} />
        </RowButton>
        <RowButton title="Reject" onClick={stop(onReject)}>
          <RejectGlyph />
        </RowButton>
      </div>

      {/* Keep dot lives at the far right so state reads even without hover. */}
      <span className="flex w-2 flex-none justify-center">
        {kept && (
          <span
            className="h-1.5 w-1.5 rounded-full"
            style={{ background: 'var(--color-amber)' }}
          />
        )}
      </span>
    </div>
  )
}

function RowButton({
  children,
  onClick,
  title,
  active,
}: {
  children: React.ReactNode
  onClick: (e: React.MouseEvent) => void
  title: string
  active?: boolean
}) {
  return (
    <button
      onClick={onClick}
      title={title}
      aria-label={title}
      className="opacity-0 transition-colors group-hover:opacity-100 focus:opacity-100"
      style={{
        color: active ? 'var(--color-amber)' : 'var(--color-dim)',
        padding: '3px',
      }}
      onMouseEnter={(e) => {
        if (!active) e.currentTarget.style.color = 'var(--color-text)'
      }}
      onMouseLeave={(e) => {
        if (!active) e.currentTarget.style.color = 'var(--color-dim)'
      }}
    >
      {children}
    </button>
  )
}

function OpenGlyph() {
  return (
    <svg
      width={13}
      height={13}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.4}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M15 3h6v6" />
      <path d="M10 14 21 3" />
      <path d="M21 14v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5" />
    </svg>
  )
}

function RejectGlyph() {
  return (
    <svg
      width={12}
      height={12}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M18 6 6 18M6 6l12 12" />
    </svg>
  )
}
