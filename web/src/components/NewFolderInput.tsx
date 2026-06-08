import { useEffect, useRef, useState } from 'react'

/* ─────────────────────────────────────────────────────────────
   Inline "name the folder" input — replaces window.prompt.
   ⏎ confirms, esc cancels.
   ───────────────────────────────────────────────────────────── */

interface Props {
  count: number
  onConfirm: (name: string) => void
  onCancel: () => void
}

export function NewFolderInput({ count, onConfirm, onCancel }: Props) {
  const [name, setName] = useState('')
  const ref = useRef<HTMLInputElement>(null)

  useEffect(() => {
    ref.current?.focus()
  }, [])

  const submit = () => {
    const n = name.trim()
    if (n) onConfirm(n)
  }

  return (
    <div className="fade-in flex items-center gap-2">
      <input
        ref={ref}
        value={name}
        onChange={(e) => setName(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') submit()
          else if (e.key === 'Escape') onCancel()
        }}
        placeholder={`folder for ${count} photo${count === 1 ? '' : 's'}…`}
        spellCheck={false}
        autoComplete="off"
        className="settings-input"
        style={{ width: 220 }}
      />
      <button
        onClick={submit}
        disabled={!name.trim()}
        className="border border-amber-ring bg-amber-wash px-3 py-[7px] font-sans text-[12px] text-amber transition-colors hover:bg-amber hover:text-ink disabled:cursor-default disabled:opacity-40"
      >
        Move
      </button>
      <button
        onClick={onCancel}
        className="px-2 py-[7px] font-sans text-[12px] text-dim transition-colors hover:text-text"
      >
        Cancel
      </button>
    </div>
  )
}
