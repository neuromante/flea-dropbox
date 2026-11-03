import QtQuick
import QtQuick.Window

// Folder picker for the Dropbox provider: a flat, keyboard-first list that
// wears the current Omarchy palette. All input arrives as one JSON argument
// after "--" so the window needs no files and no backend object.
// Result protocol: one "DBXSEL <relative path>" line per chosen folder,
// then "DBXDONE" on confirm. Closing without confirming prints nothing.
Window {
    id: win

    readonly property var input: JSON.parse(Qt.application.arguments[Qt.application.arguments.length - 1])
    readonly property var pal: Object.assign({
        background: "#101620", dark_background: "#0c1118", lighter_background: "#282d36",
        foreground: "#c2cee9", muted: "#606369", accent: "#99aed6",
        selection: "#282d36", selection_foreground: "#101620"
    }, input.colors || {})

    property alias query: field.text
    property var chosen: ({})
    property int chosenCount: 0
    property var shown: []

    title: "Dropbox cartelle escluse"
    width: 680
    height: 520
    visible: true
    color: pal.background

    function refilter() {
        const terms = field.text.toLowerCase().split(/\s+/).filter(t => t.length > 0)
        shown = input.items.filter(rel => {
            const low = rel.toLowerCase()
            return terms.every(t => low.indexOf(t) >= 0)
        })
        list.currentIndex = shown.length > 0 ? 0 : -1
    }

    function setChosen(rel, on) {
        const next = Object.assign({}, chosen)
        if (on) next[rel] = true
        else delete next[rel]
        chosen = next
        chosenCount = Object.keys(next).length
    }

    function toggleCurrent() {
        if (list.currentIndex < 0) return
        const rel = shown[list.currentIndex]
        setChosen(rel, !chosen[rel])
    }

    function selectVisible() {
        const next = Object.assign({}, chosen)
        const allOn = shown.every(rel => next[rel])
        shown.forEach(rel => { if (allOn) delete next[rel]; else next[rel] = true })
        chosen = next
        chosenCount = Object.keys(next).length
    }

    function confirm() {
        if (chosenCount === 0) return
        Object.keys(chosen).sort().forEach(rel => console.log("DBXSEL " + rel))
        console.log("DBXDONE")
        Qt.quit()
    }

    Component.onCompleted: refilter()

    Shortcut { sequences: ["Escape"]; context: Qt.ApplicationShortcut; onActivated: Qt.quit() }
    Shortcut { sequences: ["Ctrl+Return", "Ctrl+Enter"]; context: Qt.ApplicationShortcut; onActivated: win.confirm() }
    Shortcut { sequences: ["Ctrl+A"]; context: Qt.ApplicationShortcut; onActivated: win.selectVisible() }

    Column {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 14

        // Header: what this is, where it applies, how much is picked.
        Item {
            width: parent.width
            height: 40
            Column {
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                spacing: 2
                Text {
                    text: "Aggiungi alla sincronizzazione"
                    color: win.pal.accent
                    font.family: win.input.font
                    font.pixelSize: 17
                    font.bold: true
                }
                Text {
                    text: win.input.folder
                    color: win.pal.muted
                    font.family: win.input.font
                    font.pixelSize: 12
                }
            }
            Text {
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                text: win.chosenCount + " / " + win.input.items.length
                color: win.chosenCount > 0 ? win.pal.accent : win.pal.muted
                font.family: win.input.font
                font.pixelSize: 13
            }
        }

        // Search box.
        Rectangle {
            width: parent.width
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
                focus: true
                clip: true
                onTextChanged: win.refilter()

                Text {
                    visible: field.text.length === 0
                    text: "Cerca cartella…"
                    color: win.pal.muted
                    font: field.font
                }
                Keys.onPressed: event => {
                    if (event.key === Qt.Key_Down) { list.incrementCurrentIndex(); event.accepted = true }
                    else if (event.key === Qt.Key_Up) { list.decrementCurrentIndex(); event.accepted = true }
                    else if (event.key === Qt.Key_PageDown) { list.currentIndex = Math.min(list.count - 1, list.currentIndex + 8); event.accepted = true }
                    else if (event.key === Qt.Key_PageUp) { list.currentIndex = Math.max(0, list.currentIndex - 8); event.accepted = true }
                    else if ((event.key === Qt.Key_Return || event.key === Qt.Key_Enter)
                             && !(event.modifiers & Qt.ControlModifier)) { win.toggleCurrent(); event.accepted = true }
                }
            }
        }

        // Results.
        Rectangle {
            width: parent.width
            height: parent.height - 40 - 38 - 44 - parent.spacing * 3
            color: win.pal.dark_background
            border.width: 1
            border.color: win.pal.lighter_background

            ListView {
                id: list
                anchors.fill: parent
                anchors.margins: 1
                clip: true
                model: win.shown
                currentIndex: -1
                highlightMoveDuration: 0
                boundsBehavior: Flickable.StopAtBounds

                delegate: Rectangle {
                    id: row
                    required property int index
                    required property string modelData
                    readonly property int cut: modelData.lastIndexOf("/")
                    readonly property bool on: win.chosen[modelData] === true
                    width: list.width
                    height: 34
                    color: ListView.isCurrentItem ? win.pal.selection : "transparent"

                    Rectangle {
                        id: box
                        anchors.left: parent.left
                        anchors.leftMargin: 14
                        anchors.verticalCenter: parent.verticalCenter
                        width: 16
                        height: 16
                        color: row.on ? win.pal.accent : "transparent"
                        border.width: 1
                        border.color: row.on ? win.pal.accent : win.pal.muted
                        Text {
                            anchors.centerIn: parent
                            visible: row.on
                            text: "✓"
                            color: win.pal.selection_foreground
                            font.pixelSize: 12
                            font.bold: true
                        }
                    }
                    Text {
                        id: name
                        anchors.left: box.right
                        anchors.leftMargin: 12
                        anchors.verticalCenter: parent.verticalCenter
                        text: row.modelData.substring(row.cut + 1)
                        color: win.pal.foreground
                        font.family: win.input.font
                        font.pixelSize: 14
                        elide: Text.ElideRight
                        width: Math.min(implicitWidth, parent.width - 60)
                    }
                    Text {
                        anchors.left: name.right
                        anchors.leftMargin: 10
                        anchors.right: parent.right
                        anchors.rightMargin: 14
                        anchors.verticalCenter: parent.verticalCenter
                        visible: row.cut > 0
                        text: row.cut > 0 ? row.modelData.substring(0, row.cut) : ""
                        color: win.pal.muted
                        font.family: win.input.font
                        font.pixelSize: 12
                        elide: Text.ElideLeft
                    }
                    MouseArea {
                        anchors.fill: parent
                        onClicked: { list.currentIndex = row.index; win.toggleCurrent(); field.forceActiveFocus() }
                    }
                }

                Text {
                    anchors.centerIn: parent
                    visible: win.shown.length === 0
                    text: "Nessuna cartella trovata"
                    color: win.pal.muted
                    font.family: win.input.font
                    font.pixelSize: 13
                }
            }
        }

        // Footer: key hints and the one primary action.
        Item {
            width: parent.width
            height: 44
            Text {
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                text: "↑↓ naviga   ↵ spunta   ^A tutte   Esc chiudi"
                color: win.pal.muted
                font.family: win.input.font
                font.pixelSize: 12
            }
            Rectangle {
                id: go
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                width: goLabel.implicitWidth + 32
                height: 34
                color: win.chosenCount > 0 ? win.pal.accent : win.pal.lighter_background
                Text {
                    id: goLabel
                    anchors.centerIn: parent
                    text: "Sincronizza" + (win.chosenCount > 0 ? " (" + win.chosenCount + ")" : "") + "  ^↵"
                    color: win.chosenCount > 0 ? win.pal.selection_foreground : win.pal.muted
                    font.family: win.input.font
                    font.pixelSize: 13
                    font.bold: true
                }
                MouseArea { anchors.fill: parent; onClicked: win.confirm() }
            }
        }
    }
}
