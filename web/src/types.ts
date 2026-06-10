/* ─────────────────────────────────────────────────────────────
   phota — types for the minimal folder controller.
   ───────────────────────────────────────────────────────────── */

/** Summary of the active folder. `folder` is null when none is open. */
export interface Library {
  folder: string | null
  count: number
  cameras: string[]
  date_range: [string, string] | [null, null]
  series: number
  /** Count of photos per file-type label (e.g. { JPEG: 5, PNG: 2 }). */
  formats: Record<string, number>
}

/** A folder currently open in a Finder window. */
export interface FinderFolder {
  path: string
  name: string
}

/** Response from GET /api/finder-folders. `error` is 'permission' when macOS
 *  Automation access to Finder is denied. */
export interface FinderFoldersResponse {
  folders: FinderFolder[]
  error: string | null
}

/** A set of near-identical photos; `keeper` is the id to keep. */
export interface DuplicateGroup {
  ids: string[]
  keeper: string
}

/** Progress of the background index job (GET /api/index-status).
 *  `running` flips to false when scanning finishes; `count` is the final
 *  photo total (null while running), `error` is set on failure. */
export interface IndexStatus {
  running: boolean
  done: number
  total: number
  folder: string | null
  count: number | null
  error: string | null
}

/** The organize actions the controller can dispatch. */
export type OrganizeAction =
  | 'sort_by_date'
  | 'by_day'
  | 'by_camera'
  | 'by_format'
  | 'duplicates'

/** Result of POST /api/organize. Fields present depend on the action:
 *  sort_by_date → renamed; by_day/by_camera/by_format → moved + folders;
 *  duplicates → moved. */
export interface OrganizeResult {
  action: string
  renamed?: number
  moved?: number
  folders?: number
}

/** A naming scheme for the batch rename. */
export type RenameFmt = 'date_number' | 'datetime' | 'number' | 'custom'

/** Dry-run preview of a rename: total files affected + up to 3 examples. */
export interface RenamePreview {
  total: number
  examples: { from: string; to: string }[]
}

/** Whether the active folder's Finder window is kept arranged-by-name.
 *  `arranged` is null when macOS hasn't reported a known state. */
export interface FinderArranged {
  arranged: boolean | null
  error?: string | null
}

/** Result of a Finder-tidy action (cleanup / keep_on / keep_off). */
export interface FinderTidyResult {
  ok: boolean
  error?: string | null
}
