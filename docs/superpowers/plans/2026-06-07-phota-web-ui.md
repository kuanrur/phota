# phota Web Control Window — Implementation Plan

> **For agentic workers:** Execute task-by-task. Backend tasks are strict TDD (failing test first). Frontend tasks are build-then-dogfood. Mechanical scaffolding (component shells, endpoint boilerplate, Vite/Tailwind setup) is delegated to Codex; architecture, API contracts, the non-destructive boundary, and review stay with the lead. Steps use checkbox (`- [ ]`) tracking.

**Goal:** `phota` (run in any folder) opens a local browser window to find, cull, and organize that folder's photos, non-destructive until Export, with a hidden bring-your-own-key AI layer (Claude / GPT / local).

**Architecture:** Python launcher builds the index (existing engine), starts a FastAPI server on 127.0.0.1, opens the browser; the server exposes a JSON API + cached thumbnails and serves a Vite/React SPA. UI state (keep flags, albums) lives in the index; Export reuses `plan.apply_plan`. AI is provider-agnostic behind one interface.

**Tech Stack:** Existing Python engine + FastAPI/uvicorn, Pillow (thumbs), httpx (provider calls); Vite + React + TypeScript + Tailwind frontend; pytest + FastAPI TestClient; vitest (light).

**Branch:** new branch `web-ui` off `implement-phota` (so the engine is included). Becomes PR #2 (or folds into #1).

**Env:** Python 3.10 `.venv` at repo root — `source .venv/bin/activate` before any python/pytest. New deps (`fastapi`, `uvicorn`, `httpx`, `openai` optional) added to `pyproject.toml` and installed into `.venv`. Frontend deps via `npm` in `web/`.

---

## Phase A — Backend state + API (strict TDD)

### Task A1: Add deps + branch
**Files:** `pyproject.toml`
- [ ] Create branch `web-ui` off `implement-phota`.
- [ ] Add to `pyproject.toml` dependencies: `fastapi>=0.110`, `uvicorn>=0.29`, `httpx>=0.27`. Add `vitest`-side later (frontend).
- [ ] `source .venv/bin/activate && pip install -e ".[dev]"` succeeds; `python -c "import fastapi, uvicorn, httpx"` works.
- [ ] Commit: `chore: add web server deps`.

### Task A2: Index/store extensions — keep flag + albums
**Files:** `phota/store.py` (new), `tests/test_store.py` (new); extend `phota/index.py` schema.
Interface (`store.py`, operating through `Index`):
- `set_keep(idx, photo_id, keep: bool|None)`, `get_keep(idx, photo_id)`
- `create_album(idx, name)`, `list_albums(idx) -> [{name, count}]`, `delete_album(idx, name)`
- `add_to_album(idx, name, ids)`, `remove_from_album(idx, name, ids)`, `albums_for(idx, photo_id) -> [name]`
- `photos_in_album(idx, name) -> [photo_id]`
Schema additions in `index.init_schema`: `ALTER`-free — add `keep INTEGER` to the `photos` CREATE, and `CREATE TABLE IF NOT EXISTS albums(name TEXT PRIMARY KEY)`, `album_photos(album TEXT, photo_id TEXT, UNIQUE(album, photo_id))`. Add `keep` to the `Photo` dataclass (default `None`) so existing column-derivation includes it.
- [ ] **Test first** (`tests/test_store.py`): set/get keep; create/list/delete album; add/remove photos; `albums_for` and `photos_in_album` round-trip; adding a photo to an album twice is idempotent (UNIQUE).
- [ ] Run → fail → implement → pass.
- [ ] Full suite green (existing 48 + new). Confirm the `Photo` field addition didn't break index round-trip tests.
- [ ] Commit: `feat: add keep flag and albums to the index`.
**Delegate to Codex:** the mechanical schema + CRUD once the test is written by the lead.

### Task A3: Thumbnails
**Files:** `phota/thumbs.py` (new), `tests/test_thumbs.py` (new).
- `thumb_path(photo_id) -> Path` under `~/.phota/thumbs/<id>.jpg` (respect `PHOTA_DB` dir in tests: derive thumbs dir next to the db).
- `get_or_build_thumb(photo: Photo, size=256) -> Path|None`: if cached file exists return it; else render from `preview.load_preview` (grayscale is fine for v1, but render from the color preview — use `Image.open`/rawpy color thumb), save 256px JPEG, return path; `None` if unbuildable.
- [ ] **Test first:** building a thumb for a `make_jpeg` fixture creates a <=256px JPEG file; second call reuses it (mtime unchanged); unbuildable path → None.
- [ ] fail → implement → pass; full suite green.
- [ ] Commit: `feat: cached thumbnail generation`.
**Note:** thumbs dir = `Path(db_path()).parent / "thumbs"` so tests isolate via `PHOTA_DB`.

### Task A4: AI provider config in config.py
**Files:** extend `phota/config.py`, `tests/test_config.py` (new).
- `config_path() -> Path` (`~/.phota/config.json`, or next to `PHOTA_DB` in tests).
- `load_config() -> dict`, `save_ai_config(provider, api_key=None, base_url=None, model=None)` writing `{ "ai": {...} }` with file mode `0o600`.
- `ai_config() -> dict|None` (the `ai` block or None).
- `public_ai_status() -> {configured, provider, }` (never includes the key).
- [ ] **Test first:** save then `ai_config` returns the values; file mode is 600; `public_ai_status` omits `api_key`; missing file → `load_config()=={}` and `ai_config()` is None.
- [ ] fail → implement → pass; suite green.
- [ ] Commit: `feat: AI provider config storage (key never exposed)`.

### Task A5: FastAPI app — read endpoints (library, photos, series, thumb)
**Files:** `phota/server.py` (new), `tests/test_server_read.py` (new).
- `create_app(folder: str|None=None) -> FastAPI`. Store the target folder in app state.
- `GET /api/library`, `GET /api/photos` (filters: album, camera, after, before, bursts_only, keep), `GET /api/series`, `GET /api/thumb/{id}` (returns FileResponse JPEG via `thumbs`).
- Photo serialization helper → the dict shape in the spec, with `thumb_url=f"/api/thumb/{id}"` and `albums` from `store.albums_for`.
- [ ] **Test first** (TestClient, seed via `make_jpeg` + `engine.build_index`): `/api/photos` returns seeded photos; `camera`/`after`/`bursts_only`/`keep` filters narrow correctly; `/api/library` summary fields; `/api/thumb/{id}` returns `image/jpeg`; unknown id → 404.
- [ ] fail → implement → pass; suite green.
- [ ] Commit: `feat: FastAPI read endpoints (photos, library, series, thumbs)`.
**Delegate to Codex:** route boilerplate + serializers after the lead writes the tests and the photo-dict contract.

### Task A6: FastAPI — mutation endpoints (keep, albums, reveal)
**Files:** extend `phota/server.py`, `tests/test_server_actions.py` (new).
- `POST /api/photos/{id}/keep`, album CRUD + membership routes, `POST /api/reveal/{id}` (calls `subprocess.run(["open","-R",path])`, guarded behind a small `reveal(path)` function that is monkeypatched in tests — do NOT actually shell out in tests).
- [ ] **Test first:** keep set reflects in a later `/api/photos`; create album → appears in `/api/albums` with count; add/remove membership; `reveal` calls the (patched) opener with the right path; bad ids → 404.
- [ ] fail → implement → pass; suite green.
- [ ] Commit: `feat: keep/album/reveal endpoints`.

### Task A7: Export endpoint (reuses plan.apply_plan)
**Files:** extend `phota/server.py`, new `phota/exporter.py` (pure plan-building), `tests/test_export.py`.
- `exporter.build_export_plan(idx, scope, out_dir) -> Plan`: `scope` in `keepers` (keep==1), `album:<name>`, `all`. Ops are `copy` into `out_dir/<label>/filename`.
- `POST /api/export` `{scope, mode, out_dir}` → build plan → `plan.apply_plan(plan, mode)`; on `move` write `<out_dir>/export.manifest.json`; return `{count, manifest_path?}`.
- [ ] **Test first:** keepers export copies only kept photos and leaves originals; album export copies that album's members; `move` writes a manifest and originals are gone; overwrite is refused (existing apply guard).
- [ ] fail → implement → pass; suite green.
- [ ] Commit: `feat: export endpoint over apply_plan`.
**This is the non-destructive boundary — lead writes and reviews these tests personally.**

### Task A8: Launcher — bare `phota` / `phota open` starts the server
**Files:** extend `phota/cli.py`, `tests/test_launch.py`.
- Add `open` command: `phota open [dir]` → `build_index(dir or cwd)`, then start uvicorn on a free port bound to 127.0.0.1, and `webbrowser.open` the URL. Factor the "scan + serve" into a testable `launch(dir, open_browser=True, serve=True)` where tests call it with `serve=False, open_browser=False` and assert it built the index and returns the app + chosen folder.
- Make bare `phota` (no subcommand) invoke `open` on cwd: use a Typer callback with `invoke_without_command=True` that calls `open` when `ctx.invoked_subcommand is None`. Keep all existing subcommands working.
- [ ] **Test first:** `launch(tmp_photo_dir, serve=False, open_browser=False)` builds the index (photos present) and returns a FastAPI app bound to that folder; existing `scan`/`cull` subcommands still resolve (CliRunner `--help` lists them).
- [ ] fail → implement → pass; suite green.
- [ ] Commit: `feat: phota launches the web window on the current folder`.

---

## Phase B — AI providers (mocked-HTTP TDD)

### Task B1: Provider abstraction + adapters
**Files:** `phota/providers.py` (new), `tests/test_providers.py` (new).
- `class Provider(Protocol)`: `available() -> bool`, `vision: bool`, `analyze_image(path) -> dict|None`.
- `get_provider(cfg: dict|None) -> Provider|None` returns the right adapter or None.
- `AnthropicProvider(api_key, model)`: builds a messages request with a base64 image block; parses JSON `{caption,tags,subjects,aesthetic_score}`. Use `httpx` directly (or the `anthropic` SDK) — but inject the HTTP client so tests mock it.
- `OpenAIProvider(api_key, model="gpt-4o")`: chat completions with an `image_url` data URL; same parse.
- `LocalOpenAIProvider(base_url, model)`: OpenAI-compatible POST to `{base_url}/chat/completions`; `vision` flagged from config; same parse.
- [ ] **Test first:** with a mocked HTTP client, each adapter posts to the right URL with the image payload and parses a canned JSON response into the normalized dict; `get_provider` selects by `provider` key; `get_provider(None) is None`; a network error → `analyze_image` returns None.
- [ ] fail → implement → pass; suite green.
- [ ] Commit: `feat: provider-agnostic AI adapters (claude/gpt/local)`.
**Delegate to Codex:** the OpenAI + Local adapters once the lead has written the Anthropic one + the shared parse/test harness.

### Task B2: Rewrite ai.py over providers + search endpoint
**Files:** rewrite `phota/ai.py`, extend `phota/server.py`, `tests/test_ai.py` (update), `tests/test_search.py` (new).
- `analyze(photo) -> dict|None`: read `config.ai_config()` → `get_provider` → cached in `ai` table (now keyed by photo id + provider). No provider → None.
- `search(idx, query) -> set[str]|None`: None if no provider; else match query against cached captions/tags (keyword/substring) over already-analyzed photos.
- `GET /api/search?q=` → `search`; if None → `409 {detail: "AI not configured"}`.
- `GET /api/settings/ai` / `POST /api/settings/ai` (save via `config.save_ai_config`, validate provider reachability best-effort, report `vision`).
- [ ] **Test first:** monkeypatch the provider; search returns matching ids; no-config search → 409; settings POST stores config and GET never returns the key.
- [ ] fail → implement → pass; suite green.
- [ ] Commit: `feat: provider-backed analysis, semantic search, AI settings`.

---

## Phase C — Frontend SPA (build + dogfood; light vitest)

> Use the `frontend-design` skill for visual quality. Mechanical scaffolding/markup delegated to Codex; layout, interaction feel, and the cull/drag UX reviewed by the lead. After each task: `npm run build` and a manual check in the browser against the real folder.

### Task C1: Vite scaffold + Tailwind + served by FastAPI
**Files:** `web/` (Vite React-TS), `web/tailwind.config.js`, extend `phota/server.py` to mount `web/dist` at `/`.
- [ ] `npm create vite@latest web -- --template react-ts`; add Tailwind; `npm run build` → `web/dist`.
- [ ] `server.py`: if `web/dist` exists, mount it as static at `/` (StaticFiles, html=True). Backend smoke test: `GET /` returns 200 HTML when dist exists (build once in CI/dev).
- [ ] Commit: `chore: vite+react+tailwind scaffold served by the API`.
**Delegate to Codex:** the entire scaffold + Tailwind wiring.

### Task C2: API client + Library shell + header summary
**Files:** `web/src/api.ts`, `web/src/Library.tsx`, `web/src/App.tsx`.
- `api.ts`: typed `getLibrary`, `getPhotos(filters)`, `setKeep`, `albums` CRUD, `export`, `aiStatus`, `search`. One `fetch` wrapper.
- `Library`: fetch `/api/library` + `/api/photos`; render header (folder, count, date range, cameras) and a placeholder grid.
- [ ] Light vitest: `api.ts` builds correct query strings for filters.
- [ ] Build + manual: header shows the real folder's summary.
- [ ] Commit: `feat: api client + library shell`.

### Task C3: PhotoGrid + PhotoTile (thumbnails, select, keep/reject)
**Files:** `web/src/PhotoGrid.tsx`, `web/src/PhotoTile.tsx`.
- Virtualized grid (e.g. `react-window`) of tiles using `/api/thumb/{id}`. Multi-select (click/shift/cmd). Tile overlay: K=keep / X=reject calling `setKeep`, with an optimistic visual state (green ring keep, dimmed reject).
- [ ] Manual: grid renders the real 75 photos; keep/reject persists across reload.
- [ ] Commit: `feat: photo grid with keep/reject`.
**Delegate to Codex:** grid/tile markup + react-window wiring; lead tunes the interaction feel.

### Task C4: FilterBar (search + chips)
**Files:** `web/src/FilterBar.tsx`.
- Search input; chips for date range, camera (from library cameras), "bursts only", keep filter (all/keepers/undecided). Drives `Library` filter state → `getPhotos`. If `aiStatus.configured`, the search box does semantic `/api/search`; else it filters client-side by filename/camera/date.
- [ ] Manual: filters narrow the grid; camera chip lists real cameras.
- [ ] Commit: `feat: filter + search bar`.

### Task C5: AlbumSidebar + drag-to-album
**Files:** `web/src/AlbumSidebar.tsx`.
- List albums with counts (from `/api/albums`); create album; click to filter by album; drop target accepting dragged selection → `addToAlbum`. Tiles draggable (from C3).
- [ ] Manual: create an album, drag photos in, count updates, filtering by album shows them.
- [ ] Commit: `feat: albums sidebar with drag-to-album`.

### Task C6: CullMode (burst stepper)
**Files:** `web/src/CullMode.tsx`.
- Fullscreen overlay launched by "Cull bursts": iterate `/api/series` (multi-photo series), big preview, keepers pre-selected by `suggested_keeper_id`; `K` keep / `X` reject / arrows navigate; auto-advance; Esc closes. Writes via `setKeep`.
- [ ] Light vitest: keyboard handler maps K/X/arrows to the right actions on a mock series.
- [ ] Manual: stepping a real burst keeps the sharp frame with one keypress.
- [ ] Commit: `feat: cull mode burst stepper`.

### Task C7: SettingsPanel (hidden BYO-AI) + ExportDialog
**Files:** `web/src/SettingsPanel.tsx`, `web/src/ExportDialog.tsx`.
- SettingsPanel (gear): pick provider (Claude/GPT/Local); enter key or base_url+model; POST `/api/settings/ai`; show detected `vision` capability or a "text-only — can't analyze images" notice. AI UI (semantic search affordance) only renders when `aiStatus.configured`.
- ExportDialog: scope (keepers / an album / all), mode (copy/move), output folder; POST `/api/export`; show result count + manifest path.
- [ ] Manual: with no key, no AI affordances appear; after adding a key, semantic search works; export copies keepers and leaves originals.
- [ ] Commit: `feat: AI settings (BYO key) + export dialog`.

### Task C8: README rewrite + end-to-end smoke
**Files:** `README.md`, `tests/test_e2e_web.py`.
- Rewrite README around the window UX (`phota` opens the browser; find/cull/organize; Export; optional BYO-AI with Claude/GPT/local). Keep a short "scripting" note for the CLI subcommands.
- Backend e2e: launch app on a seeded folder, drive scan→keep→export via TestClient, assert keepers copied and originals intact.
- [ ] Build + full backend suite green; manual full pass on the real folder.
- [ ] Commit: `docs: README for the web window; web e2e test`.
**Delegate to Codex:** README prose draft (lead edits for voice — no em dashes), e2e scaffolding.

---

## Self-review notes
- **Spec coverage:** launcher (A8), index state (A2), thumbnails (A3), read/mutation/export API (A5–A7), AI config + providers + search (A4,B1,B2), all UI interactions find/cull/organize (C3–C7), non-destructive Export via apply_plan (A7,C7). All spec sections map to tasks.
- **Non-destructive guarantee:** only A7/exporter writes photo files, through the reviewed `apply_plan`; UI state changes (keep/albums) are index-only until Export.
- **Key safety:** key stored only in `config.json` (mode 600, A4); never returned by API (B2 test asserts redaction).
- **Type consistency:** the photo-dict contract is defined once in A5 and consumed by `api.ts` (C2); `scope`/`mode` strings match between exporter (A7) and ExportDialog (C7).
- **Out of scope** (raw editing, cloud, embeddings, mobile, faces) intentionally untasked.
