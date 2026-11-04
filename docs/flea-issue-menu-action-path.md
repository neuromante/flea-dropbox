<!-- Bozza di issue per github.com/thisisgm/flea (modulo "Feature request"). Non ancora pubblicata. -->

# Title

Plugins: let a menu-action appear only under a folder (or let the plugin decide when the menu opens)

## Before you file

- [x] The latest release does not already do this.
- [x] I searched the open issues and this is not already requested.

## What you want to do

I wrote a third-party `menu-action` plugin for Dropbox selective sync
(https://github.com/neuromante/flea-dropbox). Its actions are "Exclude from sync", "Copy Dropbox link" and
"View on dropbox.com". They only mean something for items inside the Dropbox folder.

Today `when` can filter on the number of items, on folders and on MIME types, but not on where the items are.
Flea's own discovery requests also carry no paths ("Discovery requests receive no file paths").
So the plugin's rows show in every folder's menu, and outside Dropbox they can only answer with an error.
The built-in Dropbox integration can hide its rows outside the Dropbox folder, but a plugin can't do the same.

The same problem applies to plugins for Nextcloud, Syncthing, git, rclone mounts or a project folder.
Each one has actions that only make sense inside its own tree.

## How it could work

Either of these would solve it. The first is static and keeps plugins out of the menu-opening path.

1. **A path condition in `when`**, checked by Flea against the captured selection (and against the open folder
   for the background menu):

   ```json
   "when": {"minItems": 1, "folders": true, "under": ["~/Dropbox"]}
   ```

   Every selected path must be inside one of the listed folders, compared at component boundaries after
   `~` expansion. The list could also come from a plugin setting, for example
   `"under": [{"setting": "root"}]`, so a plugin whose folder differs per user doesn't need a hard-coded path.

2. **A dynamic answer when the menu opens**: an optional request, say `{"op":"menu","paths":[...],"folder":"..."}`,
   sent only to plugins that opt in (`"menuActions": {"dynamic": true, ...}`). It would be answered with the ids
   of the declared actions to show, within a short deadline (e.g. 150 ms), and the static `when` rules would be
   used when the plugin is late. Like `when`, it could only hide declared rows, never add new ones.

## Seen elsewhere

Nautilus/Caja Python extensions (`get_file_items`) and Dolphin service menus (`X-KDE-RequiredNumberOfUrls`,
plus `X-KDE-Protocols`) let an extension decide per selection. Dropbox's own Nautilus extension uses this to
show its menu only inside the Dropbox folder.

## Where in Flea

Other (plugins, file and background menus)
