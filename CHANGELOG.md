# Changelog

All notable changes to flea-dropbox are listed here.

## 0.3.0 – 2026-11-04

### Changed
- The repository is now in English: manifest, code, comments, tests, README and docs.
- Menu labels are in English, because Flea manifests are not localized: "Exclude from Sync",
  "Dropbox Selective Sync…", "Copy Dropbox Link", "View on dropbox.com".

### Added
- Runtime texts follow Flea's language. Notifications, errors and the selective-sync window
  appear in Italian when Flea runs in Italian, otherwise in English.
- The dialog gets its language with `--lang` and its texts in the payload's `strings` field.
- Tests check that the English and Italian string tables have the same keys (44 tests in all).

## 0.2.1 – 2026-11-04

### Added
- "View on dropbox.com" in the background menu as well. It opens the current folder on
  dropbox.com, or the Dropbox home page outside Dropbox. It is hidden when several items are selected.

## 0.2.0 – 2026-11-04

### Added
- "Dropbox Selective Sync…" replaces the old "manage exclusions" action and keeps the same id, so
  existing key bindings still work. It always opens the window, even with no excluded folders and
  even outside Dropbox.
- Tree window (`picker.qml`): a tick means synced, excluded folders are marked, arrows expand folders,
  and flat search, Apply and Cancel are available.
- The tree is built breadth-first, up to 4 levels and 3000 nodes. Hidden folders are skipped, and
  excluded folders are always shown. When the node limit is hit, deep levels are cut, not top-level folders.
- Changes apply only to the top-most folders, through `dropbox-cli exclude add/remove`. A notification
  sums up the result.
- "View on dropbox.com" outside Dropbox opens https://www.dropbox.com/home.

### Fixed
- The dialog payload goes through a private file in `XDG_RUNTIME_DIR` instead of a command-line
  argument, which was limited to 128 KiB.

## 0.1.0 – 2026-11-03

First release: a port of the Strata Dropbox provider to Flea's plugin protocol.

### Added
- Four menu actions: exclude a folder from sync, manage excluded folders, copy a Dropbox link,
  and view on dropbox.com.
- JSON-lines protocol (hello, settings, run, cancel). An error fails only its own request; the
  process keeps running.
- Windows and the browser start through `systemd-run --user`, outside Flea's process group and
  memory limit.
- Plugin id `io.github.neuromante.flea-dropbox`. Install it from Git with `flea plugin add`.
- MIT license. The manifest declares every program the plugin runs.
