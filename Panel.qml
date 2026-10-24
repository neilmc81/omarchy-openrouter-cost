import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

// Dropdown for OpenRouter API cost. Reads the record update.py writes to
// $XDG_STATE_HOME/openrouter-cost/overview.json and shows the current hour,
// today, this week and this month spend, plus per-key limits & balance.

Panel {
  id: root
  moduleName: "openrouter.cost"
  ipcTarget: "openrouter.cost"
  manageIpc: false

  property var anchorItem: null
  property var hostWidget: null

  readonly property color fg: bar ? bar.foreground : Color.foreground
  readonly property color dim: Qt.darker(fg, 1.45)
  readonly property color accent: Color.accent
  readonly property string fontFamily: bar ? bar.fontFamily : Style.font.family

  readonly property string home: Quickshell.env("HOME") || ""
  readonly property string stateHome: Quickshell.env("XDG_STATE_HOME") || home + "/.local/state"
  readonly property string overviewPath: stateHome + "/openrouter-cost/overview.json"
  readonly property string updater: home + "/.config/omarchy/plugins/openrouter.cost/update.py"

  property var overview: null

  readonly property var hourRec: root.overview ? root.overview.hour : null
  readonly property var todayRec: root.overview ? root.overview.today : null
  readonly property var weekRec: root.overview ? root.overview.week : null
  readonly property var monthRec: root.overview ? root.overview.month : null
  readonly property var allRec: root.overview ? root.overview.all : null
  readonly property var limit: root.overview && root.overview.limit ? root.overview.limit : null
  readonly property var credits: root.overview && root.overview.credits ? root.overview.credits : null
  readonly property var err: root.overview ? (root.overview.error ? String(root.overview.error) : "") : "no-data"
  readonly property string updatedText: root.overview ? String(root.overview.updatedAt || "").slice(0, 19).replace("T", " ") : ""

  readonly property string limitReset: root.limit ? String(root.limit.reset || "").toUpperCase() : ""
  readonly property real limitPercent: (root.limit !== null && root.limit !== undefined) ? Math.max(0, Math.min(100, Number(root.limit.percent || 0))) : 0
  readonly property bool limitAlarming: (root.limit !== null && root.limit !== undefined) ? (Number(root.limitPercent) >= 90) === true : false

  // Every key update.py found (keyBreakdown). Older overview files only
  // have key0..key3, so fall back to those.
  readonly property var keyRows: {
    var o = root.overview
    if (!o) return []
    if (Array.isArray(o.keyBreakdown)) return o.keyBreakdown.filter(function (k) { return !!k })
    var out = []
    for (var i = 0; i < 4; i++) if (o["key" + i]) out.push(o["key" + i])
    return out
  }
  readonly property string kReset: root.keyRows.length > 0 ? String(root.keyRows[0].reset || "weekly").toUpperCase() : "WEEKLY"

  function kRowText(k) {
    if (!k) return ""
    return "" + (k.label || "key") + " · week " + root.fmtCost(k.weekly)
      + " · " + root.fmtCost(k.used) + "/" + root.fmtCost(k.limit) + " used"
  }
  function kRowPct(k) { return k ? Math.max(0, Math.min(100, Number(k.percent || 0))) : 0 }

  function refresh() {
    if (root.bar) root.bar.run(root.updater)
  }

  function costLine(rec) {
    if (!rec) return "—"
    var v = rec.cost
    if (v === null || v === undefined) return "—"
    return "" + root.fmtCost(v)
  }

  function fmtCost(v) {
    var n = Number(v || 0)
    if (n === 0) return "$0.00"
    if (n < 0.01) return "$" + n.toFixed(4)
    return "$" + n.toFixed(2)
  }

  function statusText() {
    if (root.err === "no-api-key")
      return "No API key yet. Re-run install.sh, or put it in ~/.config/openrouter-cost/key"
    if (root.err === "no-data")
      return "No data yet — run update.py once."
    if (root.err !== "")
      return "OpenRouter error: " + root.err
    return "Live from openrouter.ai"
  }

  FileView {
    path: root.overviewPath
    watchChanges: true
    printErrors: false
    onFileChanged: reload()
    onLoaded: root.parse(text())
    onLoadFailed: root.overview = null
  }

  function parse(content) {
    try {
      root.overview = JSON.parse(String(content || ""))
    } catch (e) {
      console.warn("openrouter.cost", "bad overview", e)
      root.overview = null
    }
  }

  // ------------------------------------------------------------------ popup
  KeyboardPanel {
    id: panel
    anchorItem: root.anchorItem
    owner: root.hostWidget || root
    bar: root.bar
    open: root.opened
    centerOnBar: false
    contentWidth: Math.max(280, Math.min(360, panel.availableCardWidth))
    // Grows with the key rows; past the screen height the Flickable scrolls.
    readonly property real wantedHeight: Math.max(120, col.implicitHeight + panel.verticalContentInset + 16)
    contentHeight: panel.availableCardHeight > 0 ? Math.min(panel.wantedHeight, panel.availableCardHeight) : panel.wantedHeight

    Flickable {
      id: scroll
      anchors.fill: parent
      contentWidth: width
      contentHeight: col.implicitHeight
      clip: true
      boundsBehavior: Flickable.StopAtBounds

      Column {
        id: col
        width: scroll.width
        spacing: 6

        // ---- header
        Row {
          width: parent.width
          spacing: 8
          Text {
            text: "OpenRouter Cost"
            font.family: root.fontFamily
            font.pixelSize: 13
            font.bold: true
            color: root.fg
          }
          Item { width: 100; height: 1 }
          Text {
            text: root.updatedText
            font.family: root.fontFamily
            font.pixelSize: 10
            color: root.dim
            verticalAlignment: Text.AlignVCenter
          }
        }

        // ---- windows
        Item { width: col.width; height: 34
          Text { text: "Last hour"; font.family: root.fontFamily; font.pixelSize: 12
            color: root.fg; anchors.verticalCenter: parent.verticalCenter }
          Text { text: root.costLine(root.hourRec); font.family: root.fontFamily
            font.pixelSize: 11; color: root.dim; anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter }
        }
        Item { width: col.width; height: 34
          Text { text: "Today"; font.family: root.fontFamily; font.pixelSize: 12
            color: root.fg; anchors.verticalCenter: parent.verticalCenter }
          Text { text: root.costLine(root.todayRec); font.family: root.fontFamily
            font.pixelSize: 11; color: root.dim; anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter }
        }
        Item { width: col.width; height: 34
          Text { text: "This week"; font.family: root.fontFamily; font.pixelSize: 12
            color: root.fg; anchors.verticalCenter: parent.verticalCenter }
          Text { text: root.costLine(root.weekRec); font.family: root.fontFamily
            font.pixelSize: 11; color: root.dim; anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter }
        }
        Item { width: col.width; height: 34
          Text { text: "This month"; font.family: root.fontFamily; font.pixelSize: 12
            color: root.fg; anchors.verticalCenter: parent.verticalCenter }
          Text { text: root.costLine(root.monthRec); font.family: root.fontFamily
            font.pixelSize: 11; color: root.dim; anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter }
        }
        // ---- per-key limits
        Rectangle { width: col.width; height: 2
          color: Qt.rgba(root.dim.r, root.dim.g, root.dim.b, 0.25) }
        Item { width: col.width; height: 26
          visible: root.keyRows.length > 0
          Text { text: "Key limits · " + root.kReset; font.family: root.fontFamily
            font.pixelSize: 12; font.bold: true; color: root.fg
            anchors.verticalCenter: parent.verticalCenter } }

        Repeater {
          model: root.keyRows
          delegate: Item {
            id: keyRow
            required property var modelData
            width: parent ? parent.width : 0; height: 38
            Column { spacing: 5
              Text { text: root.kRowText(keyRow.modelData); font.family: root.fontFamily
                font.pixelSize: 10; color: root.fg }
              Rectangle { width: keyRow.width; height: 5; radius: 2
                color: Qt.rgba(root.dim.r, root.dim.g, root.dim.b, 0.2)
                Rectangle { width: parent.width * (root.kRowPct(keyRow.modelData) / 100); height: parent.height
                  radius: 2; color: root.kRowPct(keyRow.modelData) >= 90 ? "tomato" : root.accent } }
            } }
        }

        // ---- account balance (shared keys count their account only once)
        Rectangle { width: col.width; height: 2
          color: Qt.rgba(root.dim.r, root.dim.g, root.dim.b, 0.25) }
        Item { width: col.width; height: 34
          Text { text: "Credit balance"; font.family: root.fontFamily; font.pixelSize: 12
            color: root.fg; anchors.verticalCenter: parent.verticalCenter }
          Text {
            text: root.err === "" && root.credits
                  && root.credits.total !== null && root.credits.total !== undefined
                  && root.credits.used !== null && root.credits.used !== undefined
                  && isFinite(Number(root.credits.total)) && isFinite(Number(root.credits.used))
                ? root.fmtCost(Number(root.credits.total) - Number(root.credits.used)) : "—"
            font.family: root.fontFamily; font.pixelSize: 12; font.bold: true
            color: root.accent; anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter }
        }
        Text { width: col.width; wrapMode: Text.WordWrap; font.family: root.fontFamily
          font.pixelSize: 10; color: root.dim
          text: root.overview && root.overview.accounts
              ? String(root.overview.keys) + " keys · " + String(root.overview.accounts)
                + (root.overview.accounts === 1 ? " account · USD" : " accounts · USD") : "" }

        // ---- status
        Rectangle { width: col.width; height: 2
          color: Qt.rgba(root.dim.r, root.dim.g, root.dim.b, 0.25) }
        Text { width: col.width; wrapMode: Text.WordWrap; font.family: root.fontFamily
          font.pixelSize: 10; color: root.dim; text: root.statusText() }

        Item { width: 1; height: 2 }
        Row {
          width: col.width; spacing: 8
          Rectangle {
            width: refreshLabel.implicitWidth + 16; height: 22; radius: 4
            color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.15)
            Text { id: refreshLabel; anchors.centerIn: parent
              text: "Refresh"; font.family: root.fontFamily; font.pixelSize: 11
              color: root.accent }
            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor
              onClicked: root.refresh() }
          }
          Text { text: "Data: openrouter.ai · hourly is local"; font.family: root.fontFamily
            font.pixelSize: 9; color: root.dim; anchors.verticalCenter: parent.verticalCenter
            width: parent.width - 90 }
        }
      }
    }
  }
}