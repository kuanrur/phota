/** Minimal hairline icon set — stroke uses currentColor, sharp feel. */

type P = { className?: string; size?: number }

const base = (size: number) => ({
  width: size,
  height: size,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.4,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
})

export function ArrowLeft({ className, size = 13 }: P) {
  return (
    <svg {...base(size)} className={className}>
      <path d="M19 12H5" />
      <path d="m12 19-7-7 7-7" />
    </svg>
  )
}

export function FolderIcon({ className, size = 13 }: P) {
  return (
    <svg {...base(size)} className={className}>
      <path d="M4 20a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h4l2 3h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2z" />
    </svg>
  )
}
