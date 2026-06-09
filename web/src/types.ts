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
