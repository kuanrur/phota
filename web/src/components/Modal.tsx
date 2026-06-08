import { useEffect } from 'react'
import { CloseIcon } from './icons'

interface ModalProps {
  title: string
  onClose: () => void
  children: React.ReactNode
  width?: number
}

export function Modal({ title, onClose, children, width = 460 }: ModalProps) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/70 fade-in"
      onMouseDown={onClose}
    >
      <div
        className="scale-in mt-[12vh] w-full border border-hairline bg-panel shadow-2xl"
        style={{ maxWidth: width }}
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-hairline px-5 py-3.5">
          <h2 className="font-serif text-[17px] italic text-text">{title}</h2>
          <button
            onClick={onClose}
            className="text-dim transition-colors hover:text-text"
            aria-label="Close"
          >
            <CloseIcon />
          </button>
        </div>
        <div className="px-5 py-5">{children}</div>
      </div>
    </div>
  )
}
