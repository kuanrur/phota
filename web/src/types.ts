export interface Photo {
  id: string
  filename: string
  captured_at: string | null
  camera: string | null
  lens: string | null
  series_id: number | null
  sharpness: number | null
  keep: boolean | null
  albums: string[]
  thumb_url: string
}

export interface Library {
  folder: string | null
  count: number
  cameras: string[]
  date_range: [string, string] | [null, null]
  series: number
}

export interface Album {
  name: string
  count: number
}

export interface Series {
  series_id: number
  photo_ids: string[]
  suggested_keeper_id: string
}

export interface AiStatus {
  configured: boolean
  provider: string | null
  vision: boolean | null
}

export type KeepFilter = 'keep' | 'reject' | 'undecided'

export interface Filters {
  camera?: string
  keep?: KeepFilter
  album?: string
  burstsOnly?: boolean
  search?: string
}

export type ExportScope = 'keepers' | 'all' | `album:${string}`
export type ExportMode = 'copy' | 'move'

export interface ExportResult {
  count: number
  manifest_path?: string
}

export type AiProvider = 'claude' | 'gpt' | 'local'
