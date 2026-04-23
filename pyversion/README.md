# pyversion (PySide6)

This folder contains the stage-1 Python migration scaffold for WinMerge.
The structure mirrors core WinMerge classes and data flow.

## Environment
Use the existing virtualenv workflow:

1. workon v1
2. python -m pip install -U pip
3. python -m pip install -r pyversion/requirements.txt

## Run
From repository root:

python pyversion/main.py

## Current scope (stage-1 + stage-2 partial)
- Main app/window skeleton mapped to CMergeApp/CMainFrame
- MergeDocument/DirDocument mapped to CMergeDoc/CDirDoc
- DiffContext/DiffWrapper/DiffThread mapped to CDiffContext/CDiffWrapper/CDiffThread
- Folder compare two-phase flow (collect phase + threaded compare phase)
- 2-way and 3-way text compare summary
- 3-way merge copy actions (L/M/R pane copy)
- Plugin pipeline hooks (unpacker/prediff)
- Option parity basics (ignore whitespace / ignore case)

## Next scope
- 3-way fine-grained merge actions by diff block range
- Folder compare integration with full plugin/filter parity
- Richer UI (actual multi-pane editors, per-diff navigation, conflict highlighting)
