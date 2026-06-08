import { useState } from 'react'
import type { AiProvider, AiStatus } from '../types'
import { api, ApiError } from '../api'
import { Modal } from './Modal'

interface SettingsProps {
  status: AiStatus | null
  onClose: () => void
  onSaved: (status: AiStatus) => void
}

const PROVIDERS: { id: AiProvider; label: string }[] = [
  { id: 'claude', label: 'Claude' },
  { id: 'gpt', label: 'GPT' },
  { id: 'local', label: 'Local' },
]

export function Settings({ status, onClose, onSaved }: SettingsProps) {
  const [provider, setProvider] = useState<AiProvider>(
    (status?.provider as AiProvider) ?? 'claude',
  )
  const [apiKey, setApiKey] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [model, setModel] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<AiStatus | null>(status)

  const isLocal = provider === 'local'

  async function save() {
    setSaving(true)
    setError(null)
    try {
      const body: Parameters<typeof api.setAiSettings>[0] = { provider }
      if (isLocal) {
        if (baseUrl.trim()) body.base_url = baseUrl.trim()
        if (model.trim()) body.model = model.trim()
      } else if (apiKey.trim()) {
        body.api_key = apiKey.trim()
      }
      const next = await api.setAiSettings(body)
      setResult(next)
      onSaved(next)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Failed to save settings')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal title="AI settings" onClose={onClose}>
      <p className="mb-4 text-[12.5px] leading-relaxed text-dim">
        AI is <span className="text-text">optional and private</span>. It powers
        semantic search and image analysis. Your key is stored locally on this
        machine and is never sent anywhere except to the provider you choose.
      </p>

      {/* Provider selector */}
      <label className="mb-1.5 block font-mono text-[10px] uppercase tracking-wide text-faint">
        Provider
      </label>
      <div className="mb-4 flex border border-hairline">
        {PROVIDERS.map((p, i) => {
          const active = provider === p.id
          return (
            <button
              key={p.id}
              onClick={() => setProvider(p.id)}
              className="flex-1 py-2 text-[12px] transition-colors"
              style={{
                background: active ? 'var(--color-amber-wash)' : 'transparent',
                color: active ? 'var(--color-amber)' : 'var(--color-dim)',
                borderLeft: i > 0 ? '1px solid var(--color-hairline)' : 'none',
              }}
            >
              {p.label}
            </button>
          )
        })}
      </div>

      {isLocal ? (
        <>
          <Field label="Base URL">
            <input
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="http://localhost:11434/v1"
              className="settings-input"
            />
          </Field>
          <Field label="Model">
            <input
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder="llava / qwen2-vl / …"
              className="settings-input"
            />
          </Field>
        </>
      ) : (
        <Field label="API key">
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder={
              result?.configured && result.provider === provider
                ? '•••••••• (saved — leave blank to keep)'
                : 'sk-…'
            }
            className="settings-input"
            autoComplete="off"
          />
        </Field>
      )}

      {error && (
        <p className="mt-3 font-mono text-[11px] text-amber">{error}</p>
      )}

      {result?.configured && (
        <div className="mt-4 border border-hairline bg-ink px-3 py-2.5 font-mono text-[11px] leading-relaxed">
          <div className="text-dim">
            provider: <span className="text-text">{result.provider}</span>
          </div>
          <div className="text-dim">
            vision:{' '}
            {result.vision ? (
              <span className="text-amber">yes</span>
            ) : (
              <span className="text-dim">
                no — text-only, can't analyze images
              </span>
            )}
          </div>
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
          onClick={save}
          disabled={saving}
          className="border border-amber bg-amber-wash px-3.5 py-1.5 text-[12px] text-amber transition-colors hover:bg-amber/20 disabled:opacity-50"
        >
          {saving ? 'Saving…' : 'Save'}
        </button>
      </div>
    </Modal>
  )
}

function Field({
  label,
  children,
}: {
  label: string
  children: React.ReactNode
}) {
  return (
    <div className="mb-3">
      <label className="mb-1.5 block font-mono text-[10px] uppercase tracking-wide text-faint">
        {label}
      </label>
      {children}
    </div>
  )
}
