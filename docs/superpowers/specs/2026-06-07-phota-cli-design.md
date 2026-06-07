# phota — customizable photo sorting CLI

Date: 2026-06-07
Status: Approved design, pre-implementation

## Purpose

A command-line tool that helps organize, sort, and find the right photo or
series from a flat dump of camera files. One tool, several workflows layered on
a shared analysis pass: pick keepers from bursts, curate sets to publish, get a
clean folder structure, and flag which raws are worth editing.

Primary photo set today: `/Users/kj/Documents/phota` (Fuji `DSCF*.JPG`, Canon
`IMG_*.CR3` raws plus `.jpeg` companions, the odd `.tiff`).

## Principles

- **Local first, AI on demand.** Cheap local heuristics by default; call a
  vision model only when a command needs semantic understanding.
- **Non-destructive by default.** Originals are never moved or deleted except by
  an explicit `apply --move`, which writes a reversible manifest.
- **Analyze once, reuse.** Expensive analysis is cached in a local SQLite index;
  re-runs only process new or changed files.

## Architecture

New repository at `/Users/kj/Documents/phota-cli`, separate from the photos.
Default target directory = the photo folder, overridable per command.

### Core engine — local analysis pass

Four stages, each producing rows in the index. Per photo:

1. **scan** — walk the directory, identify images (JPEG, CR3, TIFF), assign a
   stable content-hash id, record path/filename/size/mtime.
2. **metadata** — EXIF: capture time, camera model, lens, ISO, shutter,
   aperture, GPS. Falls back to file mtime when EXIF time is missing (flagged
   approximate).
3. **quality** — sharpness (variance of Laplacian), exposure/clipping score, and
   a perceptual hash. Computed on a downscaled preview (embedded JPEG preview for
   raws) to avoid full decode of large CR3 files.
4. **grouping** — cluster photos into bursts/series by capture-time proximity
   plus perceptual-hash similarity; assign `series_id`. Pair CR3↔jpeg of the
   same shot (by capture time / basename).

### AI vision layer — lazy, cached

Separate module using the Anthropic SDK. Produces caption, subjects, tags, and an
aesthetic score, only when a command requests it (`--ai`, or semantic `find`).
Results cached in the index keyed by photo id and model, so a photo is never
analyzed twice. Behind an interface so it can be mocked in tests. No API key or
an API error degrades gracefully: AI features skip with a clear message, local
features keep working.

### Index schema (SQLite, `~/.phota/index.db`)

- `photos`: id (content hash), path, filename, kind, size, mtime, captured_at,
  captured_approx (bool), camera, lens, iso, shutter, aperture, gps_lat,
  gps_lon, sharpness, exposure_score, phash, series_id, error, analyzed_at.
- `ai`: photo_id, caption, tags (json), subjects (json), aesthetic_score,
  ai_model, analyzed_at.
- `pairs`: raw_id, jpeg_id (same shot).

### Plans and output

Every non-`apply` command is read-only. Selection commands emit a **plan** (JSON
describing intended file operations) that can be previewed, and optionally
materialize results as copies/symlinks under `./phota-out/<workflow>/`. `apply`
is the only command that mutates; with `--move` it touches originals and writes a
reversible manifest. It refuses to overwrite existing files and requires
confirmation.

## Commands

- `phota scan [dir]` — build/update the index (incremental).
- `phota status` — summary: counts, date range, cameras, series, picks.
- `phota series` — list detected bursts with the suggested keeper per series.
- `phota cull [--ai]` — rank within each burst, mark keep/reject → plan. `--ai`
  breaks ties on aesthetics.
- `phota find "<query>"` — locate a photo by metadata filters
  (`--after`, `--before`, `--camera`, `--lens`) or semantic query (needs AI tags).
- `phota organize --by date|event|camera` — produce a folder-tree plan. `event`
  clusters by larger capture-time gaps (a session/day), distinct from a `series`
  burst which is seconds apart.
- `phota curate <name> [filters]` — assemble a named publishing set, materialize
  copies into the output dir.
- `phota edit-list` — flag raws worth editing, output symlinks for Lightroom.
- `phota apply <plan> [--move]` — execute a saved plan (the only mutating
  command).

## Data flow

`scan` → `photos` rows. Workflow commands query the index, compute a selection,
emit a plan, and optionally materialize an output folder. AI commands lazily
populate the `ai` table on first use.

## Stack

Python with: `typer` (CLI), `rich` (output), `Pillow` + `piexif` (EXIF,
jpeg/tiff), `rawpy` (CR3 previews), `opencv-python` + `numpy`
(sharpness/exposure), `imagehash` (perceptual hash), `anthropic` (vision),
stdlib `sqlite3`.

### Project structure

```
phota-cli/
  pyproject.toml
  phota/
    __init__.py
    cli.py          # typer commands
    scan.py         # walk + file ids
    metadata.py     # EXIF extraction
    quality.py      # sharpness / exposure / phash
    grouping.py     # burst / series clustering
    index.py        # sqlite read/write
    ai.py           # anthropic vision (lazy, cached, mockable)
    plan.py         # plan model + apply
    output.py       # materialize copies/symlinks, rich display
  tests/
    fixtures/
    test_*.py
```

## Error handling

- Corrupt/unreadable file: log, mark errored in index, skip, continue.
- Missing EXIF timestamp: fall back to file mtime, flag approximate.
- CR3 decode failure: try embedded preview, else keep metadata-only.
- No API key or AI error: skip AI features with a message; local features work.
- `apply`: refuse to overwrite, require confirmation, write reversible manifest.

## Testing (TDD)

Tiny generated fixture images checked into the repo (not the real raws). Unit
tests for: EXIF extraction, burst grouping with synthetic timestamps, sharp vs
blurred scoring, perceptual-hash similarity, plan generation, `apply` in a temp
dir (verify originals untouched), and incremental scan (unchanged files skipped).
AI layer mocked behind its interface.

## Out of scope (for now)

- A GUI or web interface (CLI only).
- Editing or developing raws (we only flag which to edit).
- Cloud/camera ingestion ("sourcing" new photos from external places).
- Face recognition / named-person identification.
