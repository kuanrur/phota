# phota

A Finder-folder companion for cleaning up photo folders in place.

Type `phota` in a terminal and a small control window opens in your browser.
It lists the folders you have open in Finder, you pick one, and it helps you
clean that folder where it lives. No importing, no library. The folder stays
a folder.

## Install

    pip install -e .

Requires Python 3.10 or newer. The web UI ships prebuilt in `web/dist`, so
there is no build step.

## Use

    phota              # open the window on the current folder
    phota <dir>        # open the window on a specific folder
    phota open <dir>   # same thing, explicit

The window runs on a local FastAPI server bound to 127.0.0.1 only. Each
folder gets its own library, so different folders never share state.

What it can do to a folder:

- **Sort and re-order.** Order is applied by renaming files with numeric
  prefixes (`001_`, `002_`), so it survives outside phota.
- **Group.** Create subfolders by day, camera, or file format and sort the
  photos into them.
- **Find repeats.** Near-duplicates are detected with a perceptual hash and
  flagged only. Nothing moves unless you say so.
- **Rename.** Give every photo a clean name, scoped per format if you want.
- **Tidy Finder.** Snap the folder's icons to an even grid, sorted.

Everything that touches disk is explicit and writes an undo manifest first.
`phota undo <manifest>` reverses the last change.

## AI, optional

There is a bring-your-own-key AI layer for semantic search and picking the
best shot of a burst. It supports Claude, GPT, or any local OpenAI-compatible
model. The key lives in `~/.phota/config.json` (chmod 600) and is never
exposed by the API. Without a key, no AI UI appears and everything local
still works.

## CLI, for scripting

The original subcommands still work without the window:

    phota scan <dir>       # build/update the index
    phota status           # summary
    phota series           # bursts + suggested keepers
    phota cull             # pick best per burst -> plan
    phota organize         # folder-tree plan
    phota curate           # curated selections
    phota edit-list        # raws worth editing
    phota find "sunset"    # search
    phota apply <plan>     # the only command that moves files
    phota undo <manifest>  # reverse an applied plan

## Develop

    pip install -e ".[dev]"
    pytest
