# HANDOFF – flea-dropbox

## Status

Version 0.3.0 (2026-11-04). Repository in English; runtime texts follow Flea's language (Italian or English).
0.3.0 was verified live by the user on 2026-11-04: English menu labels, Italian runtime texts and selective-sync window. Only open item: Flea issue #383.

GitHub releases v0.1.0, v0.2.0, v0.2.1 and v0.3.0 (latest) were published on 2026-11-04, with notes taken from `CHANGELOG.md`. Tags: v0.1.0 = 0fd80da, v0.2.0 = ea1ac9d, v0.2.1 = d570fcc, v0.3.0 = 512573c (CHANGELOG commit on top of the 0.3.0 code).

Previous versions: 0.2.1 was verified live by the user on 2026-11-04 (0.2.0 inside Dropbox, 0.2.1 background menu).
0.1.0 was installed and verified in Flea on 2026-11-03.

The plugin ports the Strata Dropbox provider (`~/.config/strata/providers/dropbox`) to Flea's plugin protocol,
as menu actions (`menu-action`). The original Strata provider was not modified.

## Done

- `manifest.json`: id `io.github.neuromante.flea-dropbox`, four menu actions (exclude, manage, sharelink, view).
- `bin/run`: JSON-lines protocol (hello, settings, run, cancel, EOF); errors per request without exiting the process.
  Dialog mode `--manage <folder> [--lang <xx>]` for the sync-management window.
- Windows and the browser are started with `systemd-run --user --collect --quiet`, outside Flea's process group and
  memory limit. Fallback: a new session.
- `picker.qml`: the dialog. Every visible text comes from the payload's `strings`, with English fallbacks.

## Version 0.3.0

- Repository translated to English: manifest, code and comments, tests, README, HANDOFF, `docs/`.
- Menu labels in English (Flea manifests are not localized): "Exclude from Sync", "Dropbox Selective Sync…",
  "Copy Dropbox Link", "View on dropbox.com".
- Runtime texts in `bin/run` live in `STRINGS` ("en" and "it"; `tr(key, **fmt)`). Language comes from the hello
  message's `language` field: "it" when it starts with "it", otherwise "en". Before hello: English.
- The dialog gets the language through `--lang` (the plugin passes the session language to the child process).
  Its texts travel in the payload field `strings` (keys `dlg_*`).
- Tests: 44 tests (protocol, language, build_tree, plan_changes), all passing. Keys of "en" and "it" are checked to match.

## Version 0.2.0 and 0.2.1

- Action `manage` became "Dropbox Selective Sync…" (glyph cloud-upload, same id for key bindings). It always opens
  the window, even without excluded folders and even outside Dropbox (starting folder: the selected path if it is a
  folder, otherwise `folder`, otherwise the root).
- Tree window `picker.qml`: tick = synced, excluded marked, arrow to expand, flat search, Apply/Cancel. Changes come
  back as `DBXEXCL`/`DBXINCL` lines and `DBXDONE` on qml6's stderr.
- `bin/run --manage <folder>`: `build_tree` (max 4 levels, 3000 nodes, hidden folders skipped, exclusions always
  present) and `plan_changes` (only top-most folders, validated rels) are pure functions; then
  `dropbox-cli exclude remove` / `add` with cwd "/" and a summary notification.
- `view` outside Dropbox opens https://www.dropbox.com/home.
- 0.2.1: "View on dropbox.com" also in the background menu (open folder, or the home page outside Dropbox); hidden
  when several items are selected.

## Live checks

- 2026-11-03: the user confirmed the plugin works in Flea (0.1.0).
- 2026-11-04: 0.2.0 tree window on the real Dropbox and outside-Dropbox entries (file and background menus) verified
  live. 0.2.1 verified live.
- 2026-11-04: 0.3.0 verified live (language handling).
- Plugin id renamed to `io.github.neuromante.flea-dropbox` (GitHub account neuromante).
- Public repository: https://github.com/neuromante/flea-dropbox (MIT). Installed in Flea from Git
  (`flea plugin add <url>`); to update: push, then `flea plugin update io.github.neuromante.flea-dropbox`.

## Notes

- The `access` list declares every program run (dropbox-cli, wl-copy, qml6, systemd-run, xdg-open, notify-send, fc-match).
- Flea shows no Dropbox status icons.
- Flea downloads plugins with Git without the global configuration (GIT_CONFIG_GLOBAL/NOSYSTEM): it does not use
  `gh` credentials, so a private repository cannot be installed from its URL. That is why the repository is public.
- Release flow: bump `version` in manifest.json, add a section to CHANGELOG.md, commit, annotated tag `vX.Y.Z`, push with tags, `gh release create vX.Y.Z --notes-file <section of CHANGELOG>`, then `flea plugin update io.github.neuromante.flea-dropbox`.

## Request to Flea

- Issue https://github.com/thisisgm/flea/issues/383 (2026-11-04): a path condition in the `when` of menu-actions, or a
  dynamic answer from the plugin when the menu opens. If accepted, hide the entries outside Dropbox.
- Issue https://github.com/thisisgm/flea/issues/376 (idle NVIDIA dGPU woken by Flea): fixed upstream in Flea v0.4.1
  (commit f7eee9e3f, co-authored). Verified on 2026-11-09 with Flea 0.4.1: without any wrapper Flea disables
  `nvidia_icd.json` by itself, renders on the Intel GPU and the NVIDIA card stays `suspended`. The local workaround
  (`~/.local/bin/flea-igpu` and the `.desktop` / portal D-Bus overrides that used it) was removed the same day.
