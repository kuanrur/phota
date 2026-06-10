# phota

Customizable photo-sorting CLI. Analyzes a folder once (cached in
`~/.phota/index.db`) and layers non-destructive workflows on top.

## Install

    pip install -e ".[dev]"

## Use

    phota scan ~/Documents/phota      # build/update the index
    phota status                      # summary
    phota series                      # bursts + suggested keepers
    phota cull --ai                   # pick best per burst -> plan
    phota organize --by date          # folder-tree plan
    phota curate instagram --camera X-T5
    phota edit-list                   # raws worth editing (symlinks)
    phota find "sunset" --after 2025-12-01
    phota apply phota-out/cull.json   # the only command that moves files

Nothing touches your originals until you run `apply`. `apply --move` mutates
originals and writes a reversible manifest.

Semantic `find` and `cull --ai` require `ANTHROPIC_API_KEY`; without it those
features skip and everything local still works.
