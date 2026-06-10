import json
import os
import re
import shutil
from pathlib import Path

_PREFIX = re.compile(r'^\d{3,}_')


def _strip_prefix(name):
    return _PREFIX.sub('', name)


def _safe_name(name):
    return ''.join(ch for ch in name if ch.isalnum() or ch in ' _-').strip() or 'untitled'


def manifest_path(folder):
    return Path(folder) / '.phota-undo.json'


def _write_manifest(folder, ops):
    manifest_path(folder).write_text(json.dumps({'ops': ops}, indent=2))


def apply_order(folder, ordered_paths):
    '''Rename the given files (absolute paths, in the desired order) to
    001_<name>, 002_<name>, ... each within its OWN directory. Two-phase to
    avoid collisions within the set. Refuses to overwrite a pre-existing
    (foreign) file at any final target. Rolls back fully on any failure so the
    folder is never left half-renamed. Records an undo manifest. Returns
    number renamed.'''
    folder = Path(folder)
    srcs = [Path(p) for p in ordered_paths]
    # Pre-validate: every source must exist before we move anything.
    for src in srcs:
        if not src.exists():
            raise FileNotFoundError(str(src))
    pad = max(3, len(str(len(srcs))))
    ops = []
    # phase 1: move to unique temp names (in each file's own directory)
    temps = []  # list of (tmp_path, original_src_path)
    try:
        for src in srcs:
            tmp = src.with_name('.phota_tmp_' + src.name)
            shutil.move(str(src), str(tmp))
            temps.append((tmp, src))
        # phase 2: move temps to final NNN_<stripped name> in the same dir.
        for i, (tmp, src) in enumerate(temps, start=1):
            final = src.parent / (str(i).zfill(pad) + '_' + _strip_prefix(src.name))
            # Never clobber a foreign file already occupying the final slot.
            if final.exists():
                raise FileExistsError(str(final))
            shutil.move(str(tmp), str(final))
            # Record the actual original absolute path so undo round-trips.
            ops.append({'from': str(src), 'to': str(final)})
    except BaseException:
        # Roll back: undo any final moves, then restore every temp to source.
        for op in reversed(ops):
            shutil.move(op['to'], op['from'])
        for tmp, src in temps:
            if tmp.exists():
                shutil.move(str(tmp), str(src))
        raise
    _write_manifest(folder, ops)
    return len(ops)


def rename_files(folder, renames):
    '''Rename files to new basenames within their OWN directory.

    renames: list of (abs_src, new_basename). Each dest is
    Path(src).parent / new_basename. Pre-validates BEFORE any move: every src
    exists; no two dests collide on os.path.normcase(str(dest)).casefold(); a
    dest may already exist on disk ONLY if that occupant is itself one of the
    srcs being renamed (it will vacate in phase 1, so the two-phase move makes
    it safe), otherwise FileExistsError. Then two-phase with full rollback in
    apply_order's style. Writes ONE undo manifest. Returns number moved.'''
    folder = Path(folder)
    pairs = [(Path(src), Path(src).parent / new_name) for src, new_name in renames]
    # Pre-validate: every source must exist before we move anything.
    for src, _dest in pairs:
        if not src.exists():
            raise FileNotFoundError(str(src))
    # The set of src slots that will be vacated in phase 1 -- a dest may legally
    # land on one of these (e.g. a chained swap a->b while b->c).
    src_keys = {os.path.normcase(str(src)).casefold() for src, _ in pairs}
    seen = set()
    for _src, dest in pairs:
        key = os.path.normcase(str(dest)).casefold()
        if key in seen:
            raise FileExistsError(str(dest))
        # A pre-existing dest is only OK if it is itself one of the srcs we are
        # about to move out of the way; a genuinely foreign file is refused.
        if dest.exists() and key not in src_keys:
            raise FileExistsError(str(dest))
        seen.add(key)
    ops = []
    # phase 1: move to unique temp names (in each file's own directory)
    temps = []  # list of (tmp_path, dest_path)
    try:
        for src, dest in pairs:
            tmp = src.with_name('.phota_tmp_' + src.name)
            shutil.move(str(src), str(tmp))
            temps.append((tmp, dest, src))
        # phase 2: move temps to their final destinations.
        for tmp, dest, src in temps:
            shutil.move(str(tmp), str(dest))
            ops.append({'from': str(src), 'to': str(dest)})
    except BaseException:
        # Roll back: undo any final moves, then restore every temp to source.
        for op in reversed(ops):
            shutil.move(op['to'], op['from'])
        for tmp, _dest, src in temps:
            if tmp.exists():
                shutil.move(str(tmp), str(src))
        raise
    _write_manifest(folder, ops)
    return len(ops)


def sort_into_folder(folder, subfolder_name, paths):
    '''Create folder/<subfolder_name> and move the given files into it.
    Refuses to overwrite; records an undo manifest. Returns number moved.

    Pre-validates BEFORE creating the subfolder or moving anything: two selected
    files that share a basename (e.g. two IMG_0001.jpg from different subdirs,
    or the same id sent twice) would collide on dest/<name>, so reject the whole
    request with zero filesystem mutation. The move loop is wrapped in
    try/finally so that if a move still fails mid-loop (e.g. a foreign file
    already occupies a target), the manifest of moves completed so far is always
    persisted before the exception propagates -- otherwise undo could not
    recover the already-moved files.'''
    folder = Path(folder)
    dest = folder / _safe_name(subfolder_name)
    srcs = [Path(p) for p in paths]
    # Pre-validate duplicate basenames (mirror the /api/export pre-check) so the
    # common collision is rejected before any filesystem mutation.
    seen: set[str] = set()
    for src in srcs:
        # Case-insensitive key so basenames differing only by case (which map to
        # the same file on a case-insensitive filesystem) are rejected here.
        key = os.path.normcase(src.name).casefold()
        if key in seen:
            raise FileExistsError(str(dest / src.name))
        seen.add(key)
    dest.mkdir(parents=True, exist_ok=True)
    ops = []
    try:
        for src in srcs:
            target = dest / src.name
            if target.exists():
                raise FileExistsError(str(target))
            shutil.move(str(src), str(target))
            ops.append({'from': str(src), 'to': str(target)})
    finally:
        if ops:
            _write_manifest(folder, ops)
    return len(ops)


def group_into_folders(folder, assignments):
    '''assignments: list of (subfolder_name, src_abspath). Move each src into
    folder/<safe subfolder>/<basename>. Pre-validate ALL destinations are
    free (no existing file, no two assignments to the same dest) BEFORE
    moving anything, so a failure never leaves a partial move. One undo
    manifest. Returns (moved_count, sorted_unique_subfolder_names).'''
    folder = Path(folder)
    planned = []
    for sub, src in assignments:
        src = Path(src)
        dest = folder / _safe_name(sub) / src.name
        planned.append((src, dest))
    seen = set()
    for src, dest in planned:
        # Case-insensitive key: on a case-insensitive filesystem (default macOS
        # APFS) day/IMG.JPG and day/img.jpg are the SAME file, so they must
        # collide here and reject the whole batch before any move -- otherwise
        # the second move silently overwrites the first and loses a photo.
        key = os.path.normcase(str(dest)).casefold()
        if key in seen or dest.exists():
            raise FileExistsError(str(dest))
        seen.add(key)
    ops = []
    for src, dest in planned:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dest))
        ops.append({'from': str(src), 'to': str(dest)})
    _write_manifest(folder, ops)
    return len(ops), sorted({_safe_name(s) for s, _ in assignments})


def undo_last(folder):
    '''Reverse the last recorded operation. Two-phase and overwrite-safe.

    Each op moves op['to'] back to op['from']. To stay safe we:
      * skip ops whose 'to' no longer exists (already gone),
      * refuse to clobber: if some 'from' target is occupied by a file that is
        NOT itself one of our 'to' slots (i.e. a genuinely new/foreign file),
        abort the whole undo before moving anything so we never leave a
        partial restore,
      * move two-phase (every 'to' -> unique temp, then temp -> 'from') so
        chained moves (one op's 'to' == another op's 'from', e.g. colliding
        stripped names) can't clobber each other.
    '''
    mp = manifest_path(folder)
    if not mp.exists():
        return 0
    ops = json.loads(mp.read_text())['ops']
    # Only ops whose source still exists can be undone.
    live = [op for op in ops if Path(op['to']).exists()]
    to_slots = {os.path.abspath(op['to']) for op in live}
    # Pre-pass: a 'from' target is a conflict only if it is occupied by
    # something that is not one of the slots we are about to vacate.
    for op in live:
        dst = Path(op['from'])
        if dst.exists() and os.path.abspath(str(dst)) not in to_slots:
            raise FileExistsError(str(dst))
    # Phase 1: vacate every 'to' into a unique temp.
    temps = []
    for i, op in enumerate(live):
        src = Path(op['to'])
        tmp = src.with_name('.phota_undo_tmp_%d_%s' % (i, src.name))
        shutil.move(str(src), str(tmp))
        temps.append((tmp, op['from']))
    # Phase 2: restore each temp to its original location.
    vacated_dirs = set()
    for tmp, dst in temps:
        if Path(dst).exists():
            raise FileExistsError(str(dst))
        shutil.move(str(tmp), str(dst))
        vacated_dirs.add(Path(tmp).parent)
    # Remove any subfolder of the active folder we just emptied, so an undone
    # "group into folders" leaves no empty directory behind.
    folder = Path(folder).resolve()
    for d in vacated_dirs:
        d = d.resolve()
        if d != folder and folder in d.parents:
            try:
                d.rmdir()  # only succeeds if now empty
            except OSError:
                pass
    mp.unlink()
    return len(live)
