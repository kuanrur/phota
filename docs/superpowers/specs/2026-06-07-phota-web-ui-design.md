# phota web control window — design

Date: 2026-06-07
Status: Approved design, pre-implementation
Supersedes the primary UX of the CLI spec (2026-06-07-phota-cli-design.md); the CLI engine becomes the backend.

## Purpose

Type `phota` in any folder and a browser control window pops open to **find, cull, and organize** the photos in that folder. The terminal is just the launcher; the work happens in a visual UI. Decisions are non-destructive until an explicit Export. An optional, hidden, bring-your-own-key AI layer (Claude / GPT / local LLM) adds semantic search and aesthetic ranking.

The existing analysis engine (scan, EXIF, sharpness/exposure/phash, burst grouping, SQLite index) is reused unchanged as the backend. The existing `scan/cull/organize/...` subcommands remain for scripting.

## Principles

- **Open on whatever you point at.** `phota` with no argument operates on the current working directory; `phota open <dir>` targets a specific folder. Not tied to one path.
- **Live but non-destructive.** Keep/reject and album membership are saved in the index, reflected instantly, and persist between sessions. Nothing on disk changes until Export.
- **Local and private.** Server binds to 127.0.0.1 only. No internet except calls to the AI provider the user explicitly configures.
- **AI is hidden until configured.** With no provider key, there is no AI UI; all local features still work.

## Architecture

```
`phota` (cwd)  ->  Python launcher
                     - build/update index for the folder (engine.build_index)
                     - start FastAPI server on 127.0.0.1:<port>
                     - open the browser at that URL
                          |
                   FastAPI server  <-->  ~/.phota/index.db  (+ ~/.phota/thumbs/, ~/.phota/config.json)
                     - REST/JSON API (photos, albums, actions, export, ai)
                     - serves cached thumbnails
                     - serves the built React app (static)
                          |
                   Browser window (React/Vite SPA)
```

One command, one local process. Frontend talks to the API over `fetch`.

### New/changed Python modules

```
phota/
  server.py        # FastAPI app: routes for photos/albums/actions/export/ai/thumbs + static SPA
  thumbs.py        # generate + cache 256px thumbnails under ~/.phota/thumbs/<id>.jpg
  store.py         # index read/write for UI state: keep flags, albums (extends index.py concerns)
  config.py        # (extend) read/write ~/.phota/config.json (AI provider settings)
  providers.py     # provider-agnostic AI: get_provider(cfg) -> Provider; Anthropic/OpenAI/LocalOpenAI adapters
  ai.py            # (rewrite) lazy, cached analysis using the configured provider (replaces Anthropic-only)
  cli.py           # (extend) bare `phota` and `phota open <dir>` launch the server; keep existing subcommands
web/               # Vite + React + TS + Tailwind SPA, built to web/dist (served by server.py)
```

### Index / storage extensions

- `photos` table: add column `keep INTEGER` — `NULL` = undecided, `1` = keep, `0` = reject.
- New `albums(name TEXT PRIMARY KEY)` and `album_photos(album TEXT, photo_id TEXT)` (a photo may be in multiple albums).
- AI cache stays in the existing `ai` table; add `provider TEXT` alongside `ai_model`.
- `~/.phota/config.json`: `{ "ai": { "provider": "anthropic|openai|local", "base_url": str?, "model": str?, "api_key": str? } }`, file mode `600`. The API never returns the stored key, only whether one is set and which provider.

## Backend API (all under `/api`, JSON)

- `GET /api/library` → `{ folder, count, cameras, date_range }` (header summary).
- `GET /api/photos?album=&camera=&after=&before=&bursts_only=&keep=` → list of
  `{ id, filename, captured_at, camera, series_id, sharpness, keep, albums:[...], thumb_url }`.
- `GET /api/search?q=...` → list of photo ids matching a semantic query (AI). `409` with a clear message if no AI configured.
- `GET /api/series` → `[{ series_id, photo_ids:[...], suggested_keeper_id }]`.
- `GET /api/thumb/{id}` → image/jpeg (generated + cached on first request).
- `POST /api/reveal/{id}` → open the original in Finder (`open -R` on macOS).
- `POST /api/photos/{id}/keep` `{ keep: true|false|null }` → set keep flag.
- `GET /api/albums` / `POST /api/albums` `{ name }` / `DELETE /api/albums/{name}`.
- `POST /api/albums/{name}/photos` `{ ids:[...] }` / `DELETE /api/albums/{name}/photos` `{ ids:[...] }`.
- `POST /api/export` `{ scope: "keepers"|"album:<name>"|"all", mode: "copy"|"move", out_dir }` →
  builds a plan from current state and applies it via the existing `plan.apply_plan`; returns the manifest. `move` writes a reversible manifest path.
- `GET /api/settings/ai` → `{ configured: bool, provider: str|null, vision: bool|null }` (never the key).
- `POST /api/settings/ai` `{ provider, api_key?, base_url?, model? }` → save to config; validates reachability and reports whether the model is vision-capable.

## Frontend (Vite + React + TS + Tailwind)

### Layout
A single window: left **Albums sidebar**, top **filter/search bar**, center **thumbnail grid**, bottom action strip (Cull bursts · Export). A gear opens **Settings**.

### Components
- `api.ts` — typed fetch client for the endpoints above.
- `Library` — top-level; holds filter state and selection; fetches `/api/photos`.
- `FilterBar` — search box + chips: date range, camera, "bursts only", keep filter (all/keepers/undecided).
- `AlbumSidebar` — list albums with counts; create album; drop target for drag; click to filter.
- `PhotoGrid` — virtualized grid (handles thousands); multi-select (click, shift, cmd).
- `PhotoTile` — thumbnail; keep/reject overlay (K/X); selected ring; draggable to albums.
- `CullMode` — fullscreen burst stepper: big preview, K keep / X reject (keyboard), auto-advance; pre-flags burst losers by sharpness.
- `SettingsPanel` — choose provider (Claude/GPT/Local), enter key or base URL + model; shows detected vision capability or a clear "text-only, can't analyze images" notice.
- `ExportDialog` — choose scope (keepers / an album / all), mode (copy/move), output folder; calls `/api/export`.

### Interactions (the three the user picked)
- **Find:** type in search (semantic when AI configured, else it filters by filename/camera/date) and/or apply chips; grid updates live. Click a tile → large preview + "reveal in Finder".
- **Cull bursts:** "Cull bursts" launches `CullMode`; keepers are pre-selected by sharpness, user confirms with one keypress per frame.
- **Organize:** drag selected tiles onto an album in the sidebar (or select + "Add to album"). Albums materialize as folders on Export.

## AI: provider-agnostic, hidden, BYO-key

`providers.py` exposes `get_provider(cfg) -> Provider | None` with a uniform interface:
- `available() -> bool` and `vision: bool`
- `analyze_image(path) -> { caption, tags, subjects, aesthetic_score } | None`

Adapters:
- **AnthropicProvider** — Claude vision (messages API with an image block).
- **OpenAIProvider** — GPT-4o vision (chat completions with an image_url data URL).
- **LocalOpenAIProvider** — any OpenAI-compatible `base_url` (Ollama, LM Studio, llama.cpp). Vision only if the configured model supports it; `vision` is detected/declared and surfaced in Settings.

`ai.py` is rewritten to read the configured provider, call `analyze_image` on the small preview, and cache the result in the `ai` table (keyed by photo id + provider). Semantic `search` matches the query against cached captions/tags (keyword/substring for v1; embeddings are a possible later upgrade). No provider configured → `ai` features are absent in the UI and the search endpoint returns a clear 409.

The API key is stored only in `~/.phota/config.json` (mode 600), used only to call the chosen provider, and never returned by the API or logged.

## Thumbnails

`thumbs.py` renders a 256px JPEG from the existing preview path (embedded preview for raws), cached at `~/.phota/thumbs/<id>.jpg`. `GET /api/thumb/{id}` generates on first request, then serves the file. Invalidated when a photo's id changes (content changed) — stale thumbs are pruned alongside index pruning.

## Export (the non-destructive boundary)

Export is the only path that writes photo files, and it reuses the CLI's `plan.apply_plan`:
- Build a `Plan` from current state (keepers, or an album's members, or all).
- `copy` (default) into `out_dir/<scope>/`, or `move` with a reversible manifest.
- Returns the manifest; `move` exposes an undo via the existing `reverse_manifest`.

## Testing

- **Backend (pytest + FastAPI TestClient):** photos listing + filters, keep flag set/get, album create/add/remove, export builds+applies a plan (copy leaves originals; move is reversible), thumb endpoint returns JPEG, settings save/redaction (key never returned), search returns 409 with no AI. Reuse the existing `make_jpeg` fixtures and per-test DB isolation.
- **Provider adapters:** unit-tested with mocked HTTP clients (no network); assert each adapter builds the right request and parses the response; `available()`/`vision` logic.
- **Frontend:** light vitest coverage of the api client and CullMode keyboard logic; the UI itself is dogfooded manually (it's a local tool). A backend smoke test asserts the built SPA is served at `/`.

## Out of scope (for now)

- Editing/developing raws (we only flag and organize).
- Cloud sync or multi-user.
- Embedding-based semantic search (v1 matches AI-generated tags/captions by keyword).
- Mobile/responsive layout (desktop browser only).
- Face recognition / named people.
