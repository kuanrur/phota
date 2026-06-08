import {
  DndContext,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core'
import {
  SortableContext,
  arrayMove,
  rectSortingStrategy,
} from '@dnd-kit/sortable'
import { Tile } from './Tile'
import type { Photo } from '../types'

/* ─────────────────────────────────────────────────────────────
   Screen 2 body — the sortable photo grid + a dupe banner.
   Reordering is local; persistence happens via "Apply order".
   ───────────────────────────────────────────────────────────── */

interface Props {
  photos: Photo[]
  selected: Set<string>
  dupeIds: Set<string>
  dupeGroupCount: number
  onReorder: (ids: string[]) => void
  onSelectTile: (id: string, e: React.MouseEvent) => void
  onSelectAllRepeats: () => void
}

export function Grid({
  photos,
  selected,
  dupeIds,
  dupeGroupCount,
  onReorder,
  onSelectTile,
  onSelectAllRepeats,
}: Props) {
  // 6px activation distance: a small drag starts a sort, a tap selects.
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
  )

  const ids = photos.map((p) => p.id)

  function handleDragEnd(e: DragEndEvent) {
    const { active, over } = e
    if (!over || active.id === over.id) return
    const from = ids.indexOf(String(active.id))
    const to = ids.indexOf(String(over.id))
    if (from < 0 || to < 0) return
    onReorder(arrayMove(ids, from, to))
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {dupeGroupCount > 0 && (
        <div className="flex items-center gap-3 border-b border-hairline px-5 py-2.5">
          <span className="font-sans text-[12.5px] text-dim">
            <span className="text-amber">{dupeGroupCount}</span> set
            {dupeGroupCount === 1 ? '' : 's'} of repeats
          </span>
          <button
            onClick={onSelectAllRepeats}
            className="border border-hairline px-2.5 py-1 font-sans text-[11.5px] text-text transition-colors hover:border-amber hover:text-amber"
          >
            select all repeats
          </button>
        </div>
      )}

      <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5">
        {photos.length === 0 ? (
          <div className="flex h-full items-center justify-center font-mono text-[12px] text-faint">
            no photos in this folder
          </div>
        ) : (
          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            onDragEnd={handleDragEnd}
          >
            <SortableContext items={ids} strategy={rectSortingStrategy}>
              <div
                className="grid gap-3"
                style={{
                  gridTemplateColumns:
                    'repeat(auto-fill, minmax(150px, 1fr))',
                }}
              >
                {photos.map((p, i) => (
                  <Tile
                    key={p.id}
                    photo={p}
                    index={i}
                    selected={selected.has(p.id)}
                    isDupe={dupeIds.has(p.id)}
                    onSelect={(e) => onSelectTile(p.id, e)}
                  />
                ))}
              </div>
            </SortableContext>
          </DndContext>
        )}
      </div>
    </div>
  )
}
