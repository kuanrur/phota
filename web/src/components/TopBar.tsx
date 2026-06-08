import { useEffect, useRef, useState } from 'react'
import type { AiStatus, Filters, KeepFilter, Library } from '../types'
import { ChevronDown, GearIcon, SearchIcon } from './icons'

interface TopBarProps {
  library: Library | null
  aiStatus: AiStatus | null
  filters: Filters
  searchText: string
  onSearchText: (v: string) => void
  onSubmitSearch: () => void
  searching: boolean
  onSetCamera: (camera: string | undefined) => void
  onSetKeep: (keep: KeepFilter | undefined) => void
  onToggleBursts: () => void
  onOpenSettings: () => void
}

const KEEP_OPTIONS: { label: string; value: KeepFilter | undefined }[] = [
  { label: 'All', value: undefined },
  { label: 'Keepers', value: 'keep' },
  { label: 'Undecided', value: 'undecided' },
  { label: 'Rejected', value: 'reject' },
]

export function TopBar({
  library,
  aiStatus,
  filters,
  searchText,
  onSearchText,
  onSubmitSearch,
  searching,
  onSetCamera,
  onSetKeep,
  onToggleBursts,
  onOpenSettings,
}: TopBarProps) {
  const aiOn = !!aiStatus?.configured

  return (
    <header className="flex shrink-0 items-center gap-4 border-b border-hairline bg-panel px-4 py-2.5">
      {/* Wordmark + folder + counts */}
      <div className="flex min-w-0 items-baseline gap-3">
        <span className="font-serif text-[22px] italic leading-none text-text">
          phota
        </span>
        <div className="hidden min-w-0 flex-col leading-tight sm:flex">
          <span className="truncate font-mono text-[10px] text-dim" title={library?.folder ?? ''}>
            {library?.folder ?? '—'}
          </span>
          <span className="font-mono text-[10px] text-faint">
            {library ? `${library.count} photos · ${library.series} series` : '…'}
          </span>
        </div>
      </div>

      <div className="flex-1" />

      {/* Search */}
      <div className="relative flex items-center">
        <span className="pointer-events-none absolute left-2.5 text-dim">
          <SearchIcon />
        </span>
        <input
          value={searchText}
          onChange={(e) => onSearchText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') onSubmitSearch()
          }}
          placeholder={searching ? 'searching…' : 'search…'}
          className="w-44 border border-hairline bg-ink py-1.5 pl-8 pr-14 font-mono text-[11px] text-text placeholder:text-faint focus:w-56 focus:border-amber-ring"
          style={{ transition: 'width 200ms ease-out, border-color 150ms' }}
        />
        {!aiOn && (
          <span
            className="pointer-events-none absolute right-2 font-mono text-[9px] uppercase tracking-wide text-faint"
            title="AI not configured — searching loaded photos only"
          >
            AI off
          </span>
        )}
      </div>

      {/* Camera dropdown */}
      <CameraSelect
        cameras={library?.cameras ?? []}
        value={filters.camera}
        onChange={onSetCamera}
      />

      {/* Keep filter chips */}
      <div className="flex items-center border border-hairline">
        {KEEP_OPTIONS.map((opt, i) => {
          const active = filters.keep === opt.value
          return (
            <button
              key={opt.label}
              onClick={() => onSetKeep(opt.value)}
              className="px-2.5 py-1.5 text-[11px] transition-colors"
              style={{
                background: active ? 'var(--color-amber-wash)' : 'transparent',
                color: active ? 'var(--color-amber)' : 'var(--color-dim)',
                borderLeft: i > 0 ? '1px solid var(--color-hairline)' : 'none',
              }}
            >
              {opt.label}
            </button>
          )
        })}
      </div>

      {/* Bursts toggle */}
      <button
        onClick={onToggleBursts}
        className="border border-hairline px-2.5 py-1.5 text-[11px] transition-colors"
        style={{
          background: filters.burstsOnly ? 'var(--color-amber-wash)' : 'transparent',
          color: filters.burstsOnly ? 'var(--color-amber)' : 'var(--color-dim)',
          borderColor: filters.burstsOnly ? 'var(--color-amber-ring)' : undefined,
        }}
      >
        bursts only
      </button>

      {/* Settings gear */}
      <button
        onClick={onOpenSettings}
        className="ml-1 flex h-7 w-7 items-center justify-center text-dim transition-colors hover:text-text"
        title="AI settings"
      >
        <GearIcon />
      </button>
    </header>
  )
}

function CameraSelect({
  cameras,
  value,
  onChange,
}: {
  cameras: string[]
  value?: string
  onChange: (v: string | undefined) => void
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [])

  const active = !!value

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 border border-hairline px-2.5 py-1.5 text-[11px] transition-colors"
        style={{
          background: active ? 'var(--color-amber-wash)' : 'transparent',
          color: active ? 'var(--color-amber)' : 'var(--color-dim)',
          borderColor: active ? 'var(--color-amber-ring)' : undefined,
        }}
      >
        <span className="max-w-32 truncate">{value ?? 'All cameras'}</span>
        <ChevronDown size={12} />
      </button>
      {open && (
        <div className="fade-in absolute right-0 z-30 mt-1 max-h-64 w-48 overflow-y-auto border border-hairline bg-elevated py-1 shadow-xl">
          <DropItem
            label="All cameras"
            active={!value}
            onClick={() => {
              onChange(undefined)
              setOpen(false)
            }}
          />
          {cameras.map((c) => (
            <DropItem
              key={c}
              label={c}
              active={value === c}
              onClick={() => {
                onChange(c)
                setOpen(false)
              }}
            />
          ))}
          {cameras.length === 0 && (
            <div className="px-3 py-2 font-mono text-[10px] text-faint">
              no cameras
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function DropItem({
  label,
  active,
  onClick,
}: {
  label: string
  active: boolean
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className="block w-full truncate px-3 py-1.5 text-left text-[11px] transition-colors hover:bg-panel"
      style={{ color: active ? 'var(--color-amber)' : 'var(--color-text)' }}
    >
      {label}
    </button>
  )
}
