import QtQuick
import QtQuick.Window

// Selective-sync dialog for the Dropbox provider: a flat, indented tree that
// wears the current Omarchy palette. All input arrives as one JSON argument
// after "--": {root, target, nodes:[{rel,name,depth,synced,hasChildren}],
// truncated, colors, font}; nodes come depth-first.
// Result protocol (console.log, read from stderr): "DBXEXCL <rel>" for each
// synced folder now unchecked by itself, "DBXINCL <rel>" for each excluded
// folder now checked, then "DBXDONE" on confirm. Closing prints nothing.
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
    readonly property int indentStep: 18

    // own[rel]: the folder's own checked state; a folder also needs every
    // ancestor checked to be synced (see effective()).
    property var own: ({})
    property var expanded: ({})
    property var plan: ({ excl: [], incl: [], exclTop: 0 })
    property var rows: []
    property bool filtering: false
    property string filterText: ""
    readonly property bool hasChanges: plan.excl.length + plan.incl.length > 0

    title: "Dropbox – sincronizzazione selettiva"
    width: 720
    height: 560
    visible: true
    color: pal.background

    // ---- state helpers -------------------------------------------------

    function inheritedOff(rel) {
        let cut = rel.lastIndexOf("/")
        let r = rel
        while (cut > 0) {
            r = r.substring(0, cut)
            if (r in own && own[r] !== true) return true
            cut = r.lastIndexOf("/")
        }
        return false
    }

    function effective(rel) {
        return own[rel] === true && !inheritedOff(rel)
    }

    function isExpanded(rel) {
        return expanded[rel] === true
    }

    function terms() {
        return filterText.toLowerCase().split(/\s+/).filter(t => t.length > 0)
    }

    function computePlan() {
        const excl = []
        const incl = []
        input.nodes.forEach(n => {
            if (n.synced) { if (own[n.rel] === false) excl.push(n.rel) }
            else if (effective(n.rel)) incl.push(n.rel)
        })
        excl.sort()
        incl.sort()
        const top = excl.filter(r => !excl.some(a => r.indexOf(a + "/") === 0))
        return { excl: excl, incl: incl, exclTop: top.length }
    }

    function summaryText() {
        const parts = []
        if (plan.exclTop > 0) parts.push(plan.exclTop + " da escludere")
        if (plan.incl.length > 0) parts.push(plan.incl.length + " da reincludere")
        return parts.length > 0 ? parts.join(", ") : "Nessuna modifica"
    }

    // ---- actions -------------------------------------------------------

    function toggleOwn(rel) {
        if (inheritedOff(rel)) return
        const next = Object.assign({}, own)
        next[rel] = !(own[rel] === true)
        own = next
        plan = computePlan()
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

    function confirm() {
        if (!hasChanges) return
        plan.excl.forEach(rel => console.log("DBXEXCL " + rel))
        plan.incl.forEach(rel => console.log("DBXINCL " + rel))
        console.log("DBXDONE")
        Qt.quit()
    }

    Component.onCompleted: {
        const o = {}
        input.nodes.forEach(n => { o[n.rel] = n.synced === true })
        own = o
        // Ancestors of the target are expanded so the target row is visible.
        const e = {}
        const t = input.target || ""
        let cut = t.indexOf("/")
        while (cut > 0) {
            e[t.substring(0, cut)] = true
            cut = t.indexOf("/", cut + 1)
        }
        expanded = e
        plan = computePlan()
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
                    text: "Sincronizzazione selettiva"
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
                    text: "Cerca cartella…  (/ oppure digita)"
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
                text: "↑↓ naviga   Spazio spunta   ←→ apri/chiudi   / cerca   Esc chiudi"
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
                        text: "Annulla"
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
                        text: "Applica"
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
                text: "Elenco parziale: cartelle troppo profonde o numerose"
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
                    readonly property bool isOff: win.inheritedOff(rel)
                    readonly property bool isChecked: win.effective(rel)
                    readonly property bool isOpen: win.isExpanded(rel)
                    readonly property bool differs: isChecked !== modelData.synced
                    readonly property int boxX: 30 + level * win.indentStep

                    width: list.width
                    height: 32
                    color: ListView.isCurrentItem ? win.pal.selection : "transparent"
                    opacity: isOff ? 0.5 : 1

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

                    // Checkbox: checked = will be synced.
                    Rectangle {
                        id: box
                        x: row.boxX
                        anchors.verticalCenter: parent.verticalCenter
                        width: 16
                        height: 16
                        color: row.isChecked ? win.pal.accent : "transparent"
                        border.width: 1
                        border.color: row.isChecked ? win.pal.accent : win.pal.muted
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
                        visible: row.modelData.synced === false
                        text: "esclusa"
                        color: win.pal.muted
                        font.family: win.input.font
                        font.pixelSize: 12
                    }
                }

                Text {
                    anchors.centerIn: parent
                    visible: win.rows.length === 0
                    text: "Nessuna cartella trovata"
                    color: win.pal.muted
                    font.family: win.input.font
                    font.pixelSize: 13
                }
            }
        }
    }
}
