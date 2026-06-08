interface ActionBarProps {
  selectionCount: number
  keepCount: number
  visibleCount: number
  onCull: () => void
  onExport: () => void
  onClearSelection: () => void
}

export function ActionBar({
  selectionCount,
  keepCount,
  visibleCount,
  onCull,
  onExport,
  onClearSelection,
}: ActionBarProps) {
  return (
    <footer className="flex shrink-0 items-center gap-4 border-t border-hairline bg-panel px-4 py-2">
      <div className="flex items-center gap-4 font-mono text-[11px] text-dim">
        <span>
          <span className="text-text">{visibleCount}</span> shown
        </span>
        <span>
          <span className="text-amber">{keepCount}</span> keepers
        </span>
        {selectionCount > 0 && (
          <button
            onClick={onClearSelection}
            className="text-amber transition-colors hover:text-text"
            title="Clear selection (Esc)"
          >
            {selectionCount} selected ✕
          </button>
        )}
      </div>

      <div className="flex-1" />

      <button
        onClick={onCull}
        className="border border-hairline px-3.5 py-1.5 text-[12px] text-dim transition-colors hover:border-amber-ring hover:text-text"
      >
        Cull bursts
      </button>
      <button
        onClick={onExport}
        className="border border-amber bg-amber-wash px-3.5 py-1.5 text-[12px] text-amber transition-colors hover:bg-amber/20"
      >
        Export
      </button>
    </footer>
  )
}
