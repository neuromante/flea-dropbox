import QtQuick
import QtQuick.Window
import "tree_logic.js" as Logic

// Selective-sync dialog for the Dropbox provider: a flat, indented tree that
// wears the current Omarchy palette. All input arrives as one JSON argument
// after "--": {root, target, nodes:[{rel,name,depth,synced,parent,hasChildren,
// loose?:{count,bytes,files:[{name,size}]}}], truncated, colors, font, strings};
// nodes come depth-first. Excluded folders are listed too (synced=false) with
// the subfolders Dropbox knows remotely; "loose" = files directly in such a
// folder. Every visible text comes from "strings" (keys dlg_*, already in the
// chosen language); the English defaults below are used for any key that is
// missing. The tick rules live in tree_logic.js.
// Checkbox: checked = fully synced, bar = partial (folder synced, some
// subfolders excluded), empty = excluded.
// Result protocol (console.log, read from stderr), on confirm: one
// "DBXEXCL <rel>" per node that was effectively synced and now is not, one
// "DBXINCL <rel>" per node that was not and now is (a node is synced only if
// all its ancestors are), one "DBXPART <rel>" per folder that becomes synced
// while some subfolders stay excluded (partial), then "DBXDONE". bin/run turns
// them into the minimal set of exclusions. Closing prints nothing.
Window {
    id: win

    readonly property var input: loadInput(Qt.application.arguments[Qt.application.arguments.length - 1])

    // The last argument is the payload itself or, as bin/run passes it, the path of a JSON file
    // (one argv string is capped at 128 KiB). Reading it needs QML_XHR_ALLOW_FILE_READ=1.
    function loadInput(arg) {
        if (arg.charAt(0) === "{") return JSON.parse(arg)
        const xhr = new XMLHttpRequest()
        xhr.open("GET", "file://" + arg, false)
        xhr.send()
        return JSON.parse(xhr.responseText)
    }
    readonly property var pal: Object.assign({
        background: "#101620", dark_background: "#0c1118", lighter_background: "#282d36",
        foreground: "#c2cee9", muted: "#606369", accent: "#99aed6",
        selection: "#282d36", selection_foreground: "#101620"
    }, input.colors || {})
    readonly property var tx: Object.assign({
        dlg_window_title: "Dropbox – selective sync",
        dlg_header: "Selective sync",
        dlg_filter_placeholder: "Find folder…  (/ or just type)",
        dlg_keys_hint: "↑↓ move   Space tick   ←→ open/close   / search   Esc close",
        dlg_cancel: "Cancel",
        dlg_apply: "Apply",
        dlg_excluded_tag: "excluded",
        dlg_pending_exclude: "{n} to exclude",
        dlg_pending_include: "{n} to include",
        dlg_pending_partial_one: "{names} becomes partial",
        dlg_pending_partial_many: "{names} become partial",
        dlg_partial_tag: "partial",
        dlg_no_changes: "No changes",
        dlg_truncated: "Partial list: folders too deep or too many",
        dlg_no_folders: "No folders found",
        dlg_decimal_sep: ".",
        dlg_warn_title_one: "{n} file will also be downloaded",
        dlg_warn_title_many: "{n} files will also be downloaded",
        dlg_warn_text: "Dropbox excludes only folders. The files directly in {folders} will be synced to this computer.",
        dlg_warn_more: "… and {k} more · total {size}",
        dlg_warn_hint: "To avoid downloading them, move them into a subfolder and try again.",
        dlg_warn_back: "Back",
        dlg_warn_apply: "Apply anyway"
    }, input.strings || {})
    readonly property int indentStep: 18

    // own[rel]: the folder's own tick; auto[rel]: opened as partial by a tick
    // below it. Rules and derived states: see tree_logic.js.
    readonly property var ix: Logic.buildIndex(input.nodes)
    property var own: Logic.initialOwn(input.nodes)
    property var auto: ({})
    property var expanded: ({})
    property var plan: Logic.plan(ix, input.nodes, own, auto)
    readonly property var states: plan.state
    readonly property var states0: Logic.compute(ix, Logic.initialOwn(input.nodes)).state
    property var rows: []
    property bool filtering: false
    property string filterText: ""
    property bool warning: false
    readonly property bool hasChanges: plan.excl.length + plan.incl.length > 0

    title: tx.dlg_window_title
    width: 720
    height: 560
    visible: true
    color: pal.background

    // ---- state helpers -------------------------------------------------

    function isExpanded(rel) {
        return expanded[rel] === true
    }

    function terms() {
        return filterText.toLowerCase().split(/\s+/).filter(t => t.length > 0)
    }

    // A count text from the dialog strings; "{n}" is the placeholder.
    function countText(key, n) {
        return String(tx[key]).replace("{n}", String(n))
    }

    function summaryText() {
        const parts = []
        if (plan.exclTop > 0) parts.push(countText("dlg_pending_exclude", plan.exclTop))
        if (plan.inclTop > 0) parts.push(countText("dlg_pending_include", plan.inclTop))
        if (plan.partial.length > 0)
            parts.push(String(tx[plan.partial.length === 1 ? "dlg_pending_partial_one"
                                                           : "dlg_pending_partial_many"])
                       .replace("{names}", plan.partial.join(", ")))
        return parts.length > 0 ? parts.join(" · ") : tx.dlg_no_changes
    }

    // "1.4 MB" / "1,4 MB" (decimal units, separator from the strings).
    function sizeText(bytes) {
        const units = ["B", "kB", "MB", "GB", "TB"]
        let v = bytes
        let u = 0
        while (v >= 1000 && u < units.length - 1) { v /= 1000; ++u }
        const t = (u === 0 || v >= 10) ? String(Math.round(v)) : v.toFixed(1)
        return t.replace(".", tx.dlg_decimal_sep) + " " + units[u]
    }

    function warnTotal() {
        let n = 0
        plan.warn.forEach(w => { n += w.count })
        return n
    }

    function warnTitle() {
        const n = warnTotal()
        return countText(n === 1 ? "dlg_warn_title_one" : "dlg_warn_title_many", n)
    }

    function warnText() {
        return String(tx.dlg_warn_text).replace("{folders}", plan.warn.map(w => w.rel).join(", "))
    }

    function warnMore(w) {
        return String(tx.dlg_warn_more).replace("{k}", String(w.count - w.files.length))
                                       .replace("{size}", sizeText(w.bytes))
    }

    // ---- actions -------------------------------------------------------

    function toggleOwn(rel) {
        const r = Logic.toggle(ix, own, auto, rel)
        own = r.own
        auto = r.auto
        plan = Logic.plan(ix, input.nodes, own, auto)
    }

    function setExpanded(rel, on) {
        const next = Object.assign({}, expanded)
        if (on) next[rel] = true
        else delete next[rel]
        expanded = next
        refresh(rel)
    }

    // Visible rows in tree mode: skip the subtree of every collapsed folder.
    function visibleNodes() {
        const out = []
        let hideBelow = -1
        input.nodes.forEach(n => {
            if (hideBelow >= 0) {
                if (n.depth > hideBelow) return
                hideBelow = -1
            }
            out.push(n)
            if (n.hasChildren && !isExpanded(n.rel)) hideBelow = n.depth
        })
        return out
    }

    // Rebuild the rows; keepRel (if listed) stays current, else the first row.
    function refresh(keepRel) {
        const ts = terms()
        filtering = ts.length > 0
        let list_rows
        if (filtering) {
            list_rows = input.nodes.filter(n => {
                const low = n.rel.toLowerCase()
                return ts.every(t => low.indexOf(t) >= 0)
            })
        } else {
            list_rows = visibleNodes()
        }
        rows = list_rows
        let idx = -1
        if (keepRel !== null && keepRel !== undefined)
            idx = list_rows.findIndex(n => n.rel === keepRel)
        if (idx < 0 && list_rows.length > 0) idx = 0
        list.currentIndex = idx
    }

    function moveCurrent(i) {
        if (rows.length === 0) return
        list.currentIndex = Math.max(0, Math.min(rows.length - 1, i))
    }

    function toggleCurrent() {
        const n = rows[list.currentIndex]
        if (n) toggleOwn(n.rel)
    }

    function expandCurrent() {
        const n = rows[list.currentIndex]
        if (!n || filtering || !n.hasChildren) return
        if (!isExpanded(n.rel)) setExpanded(n.rel, true)
        else moveCurrent(list.currentIndex + 1)
    }

    function collapseCurrent() {
        const n = rows[list.currentIndex]
        if (!n || filtering) return
        if (n.hasChildren && isExpanded(n.rel)) {
            setExpanded(n.rel, false)
            return
        }
        for (let i = list.currentIndex - 1; i >= 0; --i) {
            if (rows[i].depth < n.depth) { list.currentIndex = i; return }
        }
    }

    function focusFilter(text) {
        if (text.length > 0) field.text += text
        field.forceActiveFocus()
        field.cursorPosition = field.text.length
    }

    function listKey(event) {
        const k = event.key
        const plain = (event.modifiers & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier)) === 0
        let handled = true
        if (k === Qt.Key_Return || k === Qt.Key_Enter) confirm()
        else if (k === Qt.Key_Escape) {
            if (field.text.length > 0) field.text = ""
            else Qt.quit()
        }
        else if (k === Qt.Key_Down || (k === Qt.Key_J && plain)) moveCurrent(list.currentIndex + 1)
        else if (k === Qt.Key_Up || (k === Qt.Key_K && plain)) moveCurrent(list.currentIndex - 1)
        else if (k === Qt.Key_PageDown) moveCurrent(list.currentIndex + 8)
        else if (k === Qt.Key_PageUp) moveCurrent(list.currentIndex - 8)
        else if (k === Qt.Key_Home) moveCurrent(0)
        else if (k === Qt.Key_End) moveCurrent(rows.length - 1)
        else if (k === Qt.Key_Space && plain) toggleCurrent()
        else if ((k === Qt.Key_Right || k === Qt.Key_L) && plain) expandCurrent()
        else if ((k === Qt.Key_Left || k === Qt.Key_H) && plain) collapseCurrent()
        else if (k === Qt.Key_Slash && plain) focusFilter("")
        else if (plain && event.text.length === 1 && event.text >= " ") focusFilter(event.text)
        else handled = false
        event.accepted = handled
    }

    // Apply: with loose files that would also be downloaded, ask first.
    function confirm() {
        if (!hasChanges) return
        if (plan.warn.length > 0) {
            warning = true
            sheet.forceActiveFocus()
            return
        }
        finish()
    }

    function closeWarning() {
        warning = false
        list.forceActiveFocus()
    }

    function finish() {
        plan.excl.forEach(rel => console.log("DBXEXCL " + rel))
        plan.incl.forEach(rel => console.log("DBXINCL " + rel))
        plan.opened.forEach(rel => console.log("DBXPART " + rel))
        console.log("DBXDONE")
        Qt.quit()
    }

    Component.onCompleted: {
        // Ancestors of the target are expanded so the target row is visible.
        const e = {}
        const t = input.target || ""
        let cut = t.indexOf("/")
        while (cut > 0) {
            e[t.substring(0, cut)] = true
            cut = t.indexOf("/", cut + 1)
        }
        expanded = e
        refresh(t.length > 0 ? t : null)
        list.forceActiveFocus()
    }

    // ---- layout --------------------------------------------------------

    Item {
        id: content
        anchors.fill: parent
        anchors.margins: 20

        // Header: what this is, which folder is current.
        Item {
            id: header
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            height: 40
            Column {
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                spacing: 2
                Text {
                    text: win.tx.dlg_header
                    color: win.pal.accent
                    font.family: win.input.font
                    font.pixelSize: 17
                    font.bold: true
                }
                Text {
                    text: win.input.root + (win.input.target ? "/" + win.input.target : "")
                    color: win.pal.muted
                    font.family: win.input.font
                    font.pixelSize: 12
                    elide: Text.ElideMiddle
                    width: header.width
                }
            }
        }

        // Filter box.
        Rectangle {
            id: searchBox
            anchors.top: header.bottom
            anchors.topMargin: 14
            anchors.left: parent.left
            anchors.right: parent.right
            height: 38
            color: win.pal.dark_background
            border.width: 1
            border.color: field.activeFocus ? win.pal.accent : win.pal.lighter_background

            Text {
                id: glyph
                anchors.left: parent.left
                anchors.leftMargin: 12
                anchors.verticalCenter: parent.verticalCenter
                text: ""
                color: win.pal.muted
                font.family: win.input.font
                font.pixelSize: 14
            }
            TextInput {
                id: field
                anchors.left: glyph.right
                anchors.leftMargin: 10
                anchors.right: parent.right
                anchors.rightMargin: 12
                anchors.verticalCenter: parent.verticalCenter
                color: win.pal.foreground
                selectionColor: win.pal.accent
                selectedTextColor: win.pal.selection_foreground
                font.family: win.input.font
                font.pixelSize: 14
                clip: true
                onTextChanged: { win.filterText = field.text; win.refresh(null) }

                Text {
                    visible: field.text.length === 0
                    text: win.tx.dlg_filter_placeholder
                    color: win.pal.muted
                    font: field.font
                }
                Keys.onPressed: event => {
                    const k = event.key
                    if (k === Qt.Key_Down || k === Qt.Key_Up || k === Qt.Key_PageDown || k === Qt.Key_PageUp) {
                        list.forceActiveFocus()
                        win.listKey(event)
                    } else if (k === Qt.Key_Return || k === Qt.Key_Enter || k === Qt.Key_Escape) {
                        win.listKey(event)
                    }
                }
            }
        }

        // Footer: key hints and the two buttons.
        Item {
            id: footer
            anchors.bottom: parent.bottom
            anchors.left: parent.left
            anchors.right: parent.right
            height: 40
            Text {
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                text: win.tx.dlg_keys_hint
                color: win.pal.muted
                font.family: win.input.font
                font.pixelSize: 12
            }
            Row {
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                spacing: 10
                Rectangle {
                    width: cancelLabel.implicitWidth + 32
                    height: 34
                    color: "transparent"
                    border.width: 1
                    border.color: win.pal.lighter_background
                    Text {
                        id: cancelLabel
                        anchors.centerIn: parent
                        text: win.tx.dlg_cancel
                        color: win.pal.foreground
                        font.family: win.input.font
                        font.pixelSize: 13
                    }
                    MouseArea { anchors.fill: parent; onClicked: Qt.quit() }
                }
                Rectangle {
                    id: applyBtn
                    width: applyLabel.implicitWidth + 32
                    height: 34
                    color: win.hasChanges ? win.pal.accent : win.pal.lighter_background
                    Text {
                        id: applyLabel
                        anchors.centerIn: parent
                        text: win.tx.dlg_apply
                        color: win.hasChanges ? win.pal.selection_foreground : win.pal.muted
                        font.family: win.input.font
                        font.pixelSize: 13
                        font.bold: true
                    }
                    MouseArea {
                        anchors.fill: parent
                        enabled: win.hasChanges
                        onClicked: win.confirm()
                    }
                }
            }
        }

        // Status: pending changes and the truncation notice.
        Item {
            id: status
            anchors.bottom: footer.top
            anchors.bottomMargin: 8
            anchors.left: parent.left
            anchors.right: parent.right
            height: 20
            Text {
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                text: win.summaryText()
                color: win.hasChanges ? win.pal.accent : win.pal.muted
                font.family: win.input.font
                font.pixelSize: 13
            }
            Text {
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                visible: win.input.truncated === true
                text: win.tx.dlg_truncated
                color: win.pal.muted
                font.family: win.input.font
                font.pixelSize: 12
            }
        }

        // Tree (or flat filter results).
        Rectangle {
            anchors.top: searchBox.bottom
            anchors.topMargin: 14
            anchors.bottom: status.top
            anchors.bottomMargin: 8
            anchors.left: parent.left
            anchors.right: parent.right
            color: win.pal.dark_background
            border.width: 1
            border.color: win.pal.lighter_background

            ListView {
                id: list
                anchors.fill: parent
                anchors.margins: 1
                clip: true
                focus: true
                model: win.rows
                currentIndex: -1
                highlightMoveDuration: 0
                boundsBehavior: Flickable.StopAtBounds
                Keys.onPressed: event => win.listKey(event)

                delegate: Rectangle {
                    id: row
                    required property var modelData
                    required property int index
                    readonly property string rel: modelData.rel
                    readonly property int level: win.filtering ? 0 : modelData.depth
                    readonly property string state: win.states[rel] || "off"
                    readonly property bool isChecked: state === "on"
                    readonly property bool isPartial: state === "partial"
                    // Top of an excluded branch: only there the "excluded" tag shows.
                    readonly property bool isExclTop: modelData.synced === false
                        && (modelData.parent === null || win.ix.byRel[modelData.parent].synced === true)
                    readonly property bool isOpen: win.isExpanded(rel)
                    readonly property bool differs: state !== win.states0[rel]
                    readonly property int boxX: 30 + level * win.indentStep

                    width: list.width
                    height: 32
                    color: ListView.isCurrentItem ? win.pal.selection : "transparent"

                    MouseArea {
                        anchors.fill: parent
                        onClicked: list.currentIndex = row.index
                    }

                    // Expand/collapse chevron.
                    Text {
                        id: chevron
                        x: 6 + row.level * win.indentStep
                        width: 16
                        anchors.verticalCenter: parent.verticalCenter
                        horizontalAlignment: Text.AlignHCenter
                        text: row.modelData.hasChildren && !win.filtering ? (row.isOpen ? "▾" : "▸") : ""
                        color: win.pal.muted
                        font.family: win.input.font
                        font.pixelSize: 13
                    }
                    MouseArea {
                        x: 2 + row.level * win.indentStep
                        width: 24
                        height: parent.height
                        onClicked: {
                            list.currentIndex = row.index
                            if (row.modelData.hasChildren && !win.filtering) win.setExpanded(row.rel, !row.isOpen)
                        }
                    }

                    // Checkbox: check = fully synced, bar = partial, empty = excluded.
                    Rectangle {
                        id: box
                        x: row.boxX
                        anchors.verticalCenter: parent.verticalCenter
                        width: 16
                        height: 16
                        color: row.isChecked ? win.pal.accent : "transparent"
                        border.width: 1
                        border.color: (row.isChecked || row.isPartial) ? win.pal.accent : win.pal.muted
                        Rectangle {
                            anchors.centerIn: parent
                            visible: row.isPartial
                            width: 8
                            height: 2
                            color: win.pal.accent
                        }
                        Text {
                            anchors.centerIn: parent
                            visible: row.isChecked
                            text: "✓"
                            color: win.pal.selection_foreground
                            font.pixelSize: 12
                            font.bold: true
                        }
                    }
                    MouseArea {
                        x: row.boxX - 6
                        width: 28
                        height: parent.height
                        onClicked: {
                            list.currentIndex = row.index
                            win.toggleOwn(row.rel)
                        }
                    }

                    Text {
                        id: name
                        x: box.x + box.width + 10
                        anchors.verticalCenter: parent.verticalCenter
                        width: Math.min(implicitWidth, row.width - x - 110)
                        text: win.filtering ? row.rel : row.modelData.name
                        color: row.differs ? win.pal.accent : win.pal.foreground
                        font.family: win.input.font
                        font.pixelSize: 14
                        elide: Text.ElideLeft
                    }
                    Text {
                        anchors.left: name.right
                        anchors.leftMargin: 10
                        anchors.verticalCenter: parent.verticalCenter
                        visible: row.isExclTop || row.isPartial
                        text: row.isPartial ? win.tx.dlg_partial_tag : win.tx.dlg_excluded_tag
                        color: row.isPartial ? win.pal.accent : win.pal.muted
                        font.family: win.input.font
                        font.pixelSize: 12
                    }
                }

                Text {
                    anchors.centerIn: parent
                    visible: win.rows.length === 0
                    text: win.tx.dlg_no_folders
                    color: win.pal.muted
                    font.family: win.input.font
                    font.pixelSize: 13
                }
            }
        }
    }

    // Warning sheet: loose files directly in folders that become partial
    // (Dropbox excludes only folders, so these files are downloaded).
    Rectangle {
        id: dim
        anchors.fill: parent
        visible: win.warning
        color: "#cc0c1118"
        MouseArea { anchors.fill: parent }   // swallow clicks behind the sheet

        FocusScope {
            id: sheet
            anchors.centerIn: parent
            width: Math.min(520, parent.width - 40)
            height: sheetBox.height
            Keys.onPressed: event => {
                const k = event.key
                if (k === Qt.Key_Return || k === Qt.Key_Enter) { win.finish(); event.accepted = true }
                else if (k === Qt.Key_Escape) { win.closeWarning(); event.accepted = true }
            }

            Rectangle {
                id: sheetBox
                width: parent.width
                height: sheetCol.implicitHeight + 36
                color: win.pal.background
                border.width: 1
                border.color: win.pal.lighter_background

                Column {
                    id: sheetCol
                    x: 18
                    y: 18
                    width: parent.width - 36
                    spacing: 12
                    Text {
                        width: parent.width
                        text: win.warning ? win.warnTitle() : ""
                        color: "#e0b46a"
                        font.family: win.input.font
                        font.pixelSize: 15
                        font.bold: true
                        wrapMode: Text.Wrap
                    }
                    Text {
                        width: parent.width
                        text: win.warning ? win.warnText() : ""
                        color: win.pal.foreground
                        font.family: win.input.font
                        font.pixelSize: 13
                        wrapMode: Text.Wrap
                    }
                    Rectangle {
                        width: parent.width
                        height: Math.min(220, filesCol.implicitHeight + 16)
                        color: win.pal.dark_background
                        border.width: 1
                        border.color: win.pal.lighter_background
                        Flickable {
                            anchors.fill: parent
                            anchors.margins: 8
                            contentHeight: filesCol.implicitHeight
                            clip: true
                            boundsBehavior: Flickable.StopAtBounds
                            Column {
                                id: filesCol
                                width: parent.width
                                spacing: 4
                                Repeater {
                                    model: win.warning ? win.plan.warn : []
                                    delegate: Column {
                                        required property var modelData
                                        width: filesCol.width
                                        spacing: 4
                                        Text {
                                            text: modelData.rel + "/"
                                            color: win.pal.muted
                                            font.family: win.input.font
                                            font.pixelSize: 13
                                        }
                                        Repeater {
                                            model: modelData.files
                                            delegate: Item {
                                                required property var modelData
                                                width: filesCol.width
                                                height: 18
                                                Text {
                                                    anchors.left: parent.left
                                                    anchors.right: sz.left
                                                    anchors.rightMargin: 10
                                                    text: parent.modelData.name
                                                    color: win.pal.foreground
                                                    font.family: win.input.font
                                                    font.pixelSize: 13
                                                    elide: Text.ElideMiddle
                                                }
                                                Text {
                                                    id: sz
                                                    anchors.right: parent.right
                                                    text: win.sizeText(parent.modelData.size)
                                                    color: win.pal.muted
                                                    font.family: win.input.font
                                                    font.pixelSize: 13
                                                }
                                            }
                                        }
                                        Text {
                                            visible: modelData.count > modelData.files.length
                                            text: win.warnMore(modelData)
                                            color: win.pal.muted
                                            font.family: win.input.font
                                            font.pixelSize: 13
                                        }
                                    }
                                }
                            }
                        }
                    }
                    Text {
                        width: parent.width
                        text: win.tx.dlg_warn_hint
                        color: win.pal.muted
                        font.family: win.input.font
                        font.pixelSize: 13
                        wrapMode: Text.Wrap
                    }
                    Item {
                        width: parent.width
                        height: 36
                        Row {
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 10
                            Rectangle {
                                width: backLabel.implicitWidth + 32
                                height: 34
                                color: "transparent"
                                border.width: 1
                                border.color: win.pal.lighter_background
                                Text {
                                    id: backLabel
                                    anchors.centerIn: parent
                                    text: win.tx.dlg_warn_back
                                    color: win.pal.foreground
                                    font.family: win.input.font
                                    font.pixelSize: 13
                                }
                                MouseArea { anchors.fill: parent; onClicked: win.closeWarning() }
                            }
                            Rectangle {
                                width: anywayLabel.implicitWidth + 32
                                height: 34
                                color: win.pal.accent
                                Text {
                                    id: anywayLabel
                                    anchors.centerIn: parent
                                    text: win.tx.dlg_warn_apply
                                    color: win.pal.selection_foreground
                                    font.family: win.input.font
                                    font.pixelSize: 13
                                    font.bold: true
                                }
                                MouseArea { anchors.fill: parent; onClicked: win.finish() }
                            }
                        }
                    }
                }
            }
        }
    }
}
