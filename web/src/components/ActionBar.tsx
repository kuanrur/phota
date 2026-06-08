import { useState } from 'react'
import { NewFolderInput } from './NewFolderInput'
import { PlusIcon } from './icons'

/* ─────────────────────────────────────────────────────────────
   Screen 2 bottom toolbar — apply order, sort selection into a
   new folder, and a live selection count.
   ───────────────────────────────────────────────────────────── */

interface Props {
  selectedCount: number
  orderDirty: boolean
  busy: boolean
  flash: string | null
  onApplyOrder: () => void
  onSortInto: (name: string) => void
}

export function ActionBar({
  selectedCount,
  orderDirty,
  busy,
  flash,
  onApplyOrder,
  onSortInto,
}: Props) {
  const [naming, setNaming] = useState(false)

  return (
    <div className="flex items-center gap-3 border-t border-hairline px-5 py-3">
      <button
        onClick={onApplyOrder}
        disabled={!orderDirty || busy}
        className="border px-3 py-1.5 font-sans text-[12.5px] transition-colors disabled:cursor-default"
        style={{
          borderColor: orderDirty ? 'var(--color-amber)' : 'var(--color-hairline)',
          background: orderDirty ? 'var(--color-amber-wash)' : 'transparent',
          color: orderDirty ? 'var(--color-amber)' : 'var(--color-faint)',
        }}
      >
        Apply order
      </button>

      {naming ? (
        <NewFolderInput
          count={selectedCount}
          onConfirm={(name) => {
            setNaming(false)
            onSortInto(name)
          }}
          onCancel={() => setNaming(false)}
        />
      ) : (
        <button
          onClick={() => setNaming(true)}
          disabled={selectedCount === 0 || busy}
          className="flex items-center gap-1.5 border border-hairline px-3 py-1.5 font-sans text-[12.5px] text-text transition-colors hover:border-amber hover:text-amber disabled:cursor-default disabled:border-hairline disabled:text-faint disabled:hover:text-faint"
        >
          <PlusIcon size={12} />
          New folder…
        </button>
      )}

      <div className="ml-auto flex items-center gap-4 font-mono text-[11px]">
        {flash && <span className="text-amber">{flash}</span>}
        <span className="text-dim">
          {selectedCount} selected
        </span>
      </div>
    </div>
  )
}
