# Dropbox Selective Sync (Flea plugin)

A plugin for the [Flea](https://github.com/thisisgm/flea) file manager that adds Dropbox actions to the file menu:

- **Exclude from Sync**: excludes the selected folders from Dropbox sync (`dropbox-cli exclude add`).
- **Dropbox Selective Sync…**: opens a tree window with all the local folders of your Dropbox (up to 4 levels),
  ticked when they are synced. Unticking a folder excludes it from sync; ticking an excluded folder syncs it again.
  Also available from the background menu of the open folder; the window opens on the selected folder with its
  parent folders expanded.
- **Copy Dropbox Link**: creates share links for up to 10 items and copies them to the clipboard.
- **View on dropbox.com**: opens the selected item in the browser (one item only) or, from the background menu,
  the open folder. Outside the Dropbox folder it opens the dropbox.com home page.

The plugin is written in Python (standard library only) and uses `dropbox-cli` and the Dropbox client you already
have installed. The Dropbox folder is read from `~/.dropbox/info.json`.

Menu labels are in English, because Flea manifests are not localized. Runtime texts (replies, notifications and the
selective-sync window) follow Flea's language: Italian when Flea uses Italian, English otherwise.

## Selective-sync window

- Indented tree: the arrow (▸/▾) opens or closes a folder; the box shows whether the folder will be synced.
- Keys: ↑↓ or j/k to move, Space to tick or untick, ←→ or h/l to close or open (← on a closed folder jumps to
  its parent), `/` or simply typing to search, Enter to apply, Esc to close without changes.
- Unticking a folder disables its subfolders, which return to their previous state when the folder is ticked
  again. An excluded folder is marked "excluded"; changes relative to the starting state are shown in the accent
  colour.
- Search shows a flat list of every folder whose path contains all the typed terms.
- Apply runs `dropbox-cli exclude remove` and `exclude add` and shows a summary in the notifications. Cancel changes
  nothing.
- If the list is truncated (more than 3000 folders or more than 4 levels) the window says so; excluded folders
  always appear, even if they are deeper.

## Requirements

- Flea with plugin support (protocol 1).
- Python 3 (`/usr/bin/python3`).
- `dropbox-cli` at `/usr/bin/dropbox-cli`, with the Dropbox client running.
- `qml6` (for the sync window), `wl-copy` (for the clipboard) and `systemd-run` (to start windows outside Flea's process).

## Installation

From GitHub:

```sh
flea plugin add https://github.com/neuromante/flea-dropbox.git
flea plugin enable io.github.neuromante.flea-dropbox
```

From a local folder:

```sh
flea plugin validate "$PWD" && flea plugin add "$PWD" && flea plugin enable io.github.neuromante.flea-dropbox
```

## Update and removal

Installed from GitHub: `flea plugin update io.github.neuromante.flea-dropbox` downloads the latest published version.
Installed from a folder: `flea plugin update` does not apply; remove the plugin and repeat add and enable.

To remove it:

```sh
flea plugin remove io.github.neuromante.flea-dropbox
```

## Limits

- Flea does not show sync status icons, so the plugin does not display the sync state of files.
- The menu entries appear everywhere, because Flea does not filter menus by path: outside the Dropbox folder,
  "Dropbox Selective Sync…" opens the window on the root, "View on dropbox.com" opens the dropbox.com home page,
  while "Exclude from Sync" and "Copy Dropbox Link" answer with the error "The path is not inside the Dropbox folder.".
  The path-based menu condition is requested from Flea upstream:
  https://github.com/thisisgm/flea/issues/383
- The sync window shows at most 4 levels and 3000 folders; the list may be partial.
- Exclusions apply to folders; the main Dropbox folder itself cannot be excluded.
- Windows and the browser are started with `systemd-run --user`; without a user systemd the plugin falls back to
  starting them in a new session.
- Each request must finish within Flea's 30-second limit; copying links stops after about 25 seconds.

## Tests

```sh
python3 -m unittest discover -s tests -v
```

The tests start `bin/run` with a fake `dropbox-cli` and a temporary Dropbox folder. They open no windows
(`FLEA_DROPBOX_NO_SPAWN=1`). They also check that the English and Italian texts have the same keys.

Environment variables for the tests: `FLEA_DROPBOX_CLI`, `FLEA_DROPBOX_INFO`, `FLEA_DROPBOX_NO_SPAWN=1`.

See [CHANGELOG.md](CHANGELOG.md) for the release history.

## License

MIT. Author: lorenzo nizzi grifi gargiolli.
