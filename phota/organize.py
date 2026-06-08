import json
import re
import shutil
from pathlib import Path

_PREFIX = re.compile(r'^\d{3,}_')


def _strip_prefix(name):
    return _PREFIX.sub('', name)


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


def undo_last(folder):
    mp = manifest_path(folder)
    if not mp.exists():
        return 0
    ops = json.loads(mp.read_text())['ops']
    for op in reversed(ops):
        if Path(op['to']).exists():
            shutil.move(op['to'], op['from'])
    mp.unlink()
    return len(ops)
