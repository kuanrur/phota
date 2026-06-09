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

/** Result of POST /api/organize. Fields present depend on the action:
 *  sort_by_date → renamed; by_day/by_camera → moved + folders;
 *  duplicates → moved. */
export interface OrganizeResult {
  action: string
  renamed?: number
  moved?: number
  folders?: number
}
