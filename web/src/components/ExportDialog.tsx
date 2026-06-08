import { useState } from 'react'
import type { Album, ExportMode, ExportResult, ExportScope } from '../types'
import { api, ApiError } from '../api'
import { Modal } from './Modal'

interface ExportDialogProps {
  albums: Album[]
  keepCount: number
  totalCount: number
  onClose: () => void
}

type ScopeKind = 'keepers' | 'all' | 'album'

export function ExportDialog({
  albums,
  keepCount,
  totalCount,
  onClose,
}: ExportDialogProps) {
  const [scopeKind, setScopeKind] = useState<ScopeKind>('keepers')
  const [albumName, setAlbumName] = useState(albums[0]?.name ?? '')
  const [mode, setMode] = useState<ExportMode>('copy')
  const [outDir, setOutDir] = useState('phota-out')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<ExportResult | null>(null)

  function resolveScope(): ExportScope | null {
    if (scopeKind === 'keepers') return 'keepers'
    if (scopeKind === 'all') return 'all'
    if (!albumName) return null
    return `album:${albumName}`
  }

  async function run() {
    const scope = resolveScope()
    if (!scope) {
      setError('Pick an album to export.')
      return
    }
    setBusy(true)
    setError(null)
    setResult(null)
    try {
      const res = await api.export(scope, mode, outDir.trim() || 'phota-out')
      setResult(res)
    } catch (e) {
      setError(
        e instanceof ApiError ? e.message : 'Export failed unexpectedly.',
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal title="Export" onClose={onClose}>
      {/* Scope */}
      <label className="mb-1.5 block font-mono text-[10px] uppercase tracking-wide text-faint">
        Scope
      </label>
      <div className="mb-2 flex border border-hairline">
        <SegBtn
          active={scopeKind === 'keepers'}
          onClick={() => setScopeKind('keepers')}
          label={`Keepers (${keepCount})`}
        />
        <SegBtn
          active={scopeKind === 'album'}
          onClick={() => setScopeKind('album')}
          label="Album"
          disabled={albums.length === 0}
        />
        <SegBtn
          active={scopeKind === 'all'}
          onClick={() => setScopeKind('all')}
          label={`All (${totalCount})`}
        />
      </div>

      {scopeKind === 'album' && (
        <select
          value={albumName}
          onChange={(e) => setAlbumName(e.target.value)}
          className="settings-input mb-3"
        >
          {albums.map((a) => (
            <option key={a.name} value={a.name}>
              {a.name} ({a.count})
            </option>
          ))}
        </select>
      )}

      {/* Mode */}
      <label className="mb-1.5 mt-2 block font-mono text-[10px] uppercase tracking-wide text-faint">
        Mode
      </label>
      <div className="mb-1.5 flex border border-hairline">
        <SegBtn active={mode === 'copy'} onClick={() => setMode('copy')} label="Copy" />
        <SegBtn active={mode === 'move'} onClick={() => setMode('move')} label="Move" />
      </div>
      <p className="mb-4 font-mono text-[10px] leading-relaxed text-faint">
        {mode === 'move'
          ? 'Move writes a reversible manifest so the operation can be undone.'
          : 'Copy leaves originals untouched.'}
      </p>

      {/* Output folder */}
      <label className="mb-1.5 block font-mono text-[10px] uppercase tracking-wide text-faint">
        Output folder
      </label>
      <input
        value={outDir}
        onChange={(e) => setOutDir(e.target.value)}
        placeholder="phota-out"
        className="settings-input"
      />

      {error && <p className="mt-3 font-mono text-[11px] text-amber">{error}</p>}

      {result && (
        <div className="mt-4 border border-hairline bg-ink px-3 py-2.5 font-mono text-[11px] leading-relaxed">
          <div className="text-amber">
            exported {result.count} {result.count === 1 ? 'file' : 'files'}
          </div>
          {result.manifest_path && (
            <div className="mt-1 break-all text-dim">
              manifest: <span className="text-text">{result.manifest_path}</span>
            </div>
          )}
        </div>
      )}

      <div className="mt-5 flex justify-end gap-2">
        <button
          onClick={onClose}
          className="border border-hairline px-3.5 py-1.5 text-[12px] text-dim transition-colors hover:text-text"
        >
          Close
        </button>
        <button
          onClick={run}
          disabled={busy}
          className="border border-amber bg-amber-wash px-3.5 py-1.5 text-[12px] text-amber transition-colors hover:bg-amber/20 disabled:opacity-50"
        >
          {busy ? 'Exporting…' : 'Export'}
        </button>
      </div>
    </Modal>
  )
}

function SegBtn({
  active,
  onClick,
  label,
  disabled,
}: {
  active: boolean
  onClick: () => void
  label: string
  disabled?: boolean
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="flex-1 border-l border-hairline py-2 text-[12px] transition-colors first:border-l-0 disabled:cursor-not-allowed disabled:opacity-40"
      style={{
        background: active ? 'var(--color-amber-wash)' : 'transparent',
        color: active ? 'var(--color-amber)' : 'var(--color-dim)',
      }}
    >
      {label}
    </button>
  )
}
