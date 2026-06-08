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
    001_<name>, 002_<name>, ... in their folder. Two-phase to avoid
    collisions. Records an undo manifest. Returns number renamed.'''
    folder = Path(folder)
    pad = max(3, len(str(len(ordered_paths))))
    ops = []
    # phase 1: move to unique temp names
    temps = []
    for src in ordered_paths:
        src = Path(src)
        tmp = src.with_name('.phota_tmp_' + src.name)
        shutil.move(str(src), str(tmp))
        temps.append((tmp, src.name))
    # phase 2: move temps to final NNN_<stripped name>
    for i, (tmp, orig_name) in enumerate(temps, start=1):
        final = folder / (str(i).zfill(pad) + '_' + _strip_prefix(orig_name))
        shutil.move(str(tmp), str(final))
        ops.append({'from': str(folder / orig_name), 'to': str(final)})
    _write_manifest(folder, ops)
    return len(ops)


def sort_into_folder(folder, subfolder_name, paths):
    '''Create folder/<subfolder_name> and move the given files into it.
    Refuses to overwrite; records an undo manifest. Returns number moved.'''
    folder = Path(folder)
    dest = folder / _safe_name(subfolder_name)
    dest.mkdir(parents=True, exist_ok=True)
    ops = []
    for src in paths:
        src = Path(src)
        target = dest / src.name
        if target.exists():
            raise FileExistsError(str(target))
        shutil.move(str(src), str(target))
        ops.append({'from': str(src), 'to': str(target)})
    _write_manifest(folder, ops)
    return len(ops)


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
    for tmp, dst in temps:
        if Path(dst).exists():
            raise FileExistsError(str(dst))
        shutil.move(str(tmp), str(dst))
    mp.unlink()
    return len(live)
