import QtQuick
import Quickshell
import Quickshell.Io
import qs.Ui

// OpenRouter API cost tracker: one bar icon showing today's spend, a dropdown
// with hourly/daily/weekly/monthly usage & cost on click.
// Data comes from the record update.py writes to
// $XDG_STATE_HOME/openrouter-cost/overview.json, watched live.

BarWidget {
  id: root
  moduleName: "openrouter.cost"

  readonly property string home: Quickshell.env("HOME") || ""
  readonly property string stateHome: Quickshell.env("XDG_STATE_HOME") || home + "/.local/state"
  readonly property string overviewPath: stateHome + "/openrouter-cost/overview.json"

  property var overview: null

  readonly property string updater: home + "/.config/omarchy/plugins/openrouter.cost/update.py"

  // Shape contract for the bar's popup routing (see clock BarWidget).
  readonly property bool opened: panelLoader.item ? panelLoader.item.opened === true : false
  readonly property bool popoutSwitchClosing: panelLoader.item ? panelLoader.item.popoutSwitchClosing === true : false

  function open() { if (panelLoader.item) panelLoader.item.open() }
  function close() { if (panelLoader.item) panelLoader.item.close() }
  function closeForPopoutSwitch() { if (panelLoader.item) panelLoader.item.closeForPopoutSwitch() }

  function togglePanel() {
    if (panelLoader.item) panelLoader.item.toggle()
  }

  // Bar label: today's spend, a – while data is missing, or a warning glyph on error.
  readonly property string barText: root.barButtonText()

  function barButtonText() {
    var o = root.overview;
    if (o && o.error === "no-api-key") { return "⚠"; }
    if (o && o.error !== null && o.error !== "") { return "!"; }
    return "OR";
  }

  function fmtUsd(v) {
    var n = Number(v || 0)
    if (n === 0) return "$0.00"
    if (n < 0.01) return "$" + n.toFixed(4)
    return "$" + n.toFixed(2)
  }

  function parse(content) {
    try {
      root.overview = JSON.parse(String(content || ""))
    } catch (e) {
      root.overview = null
    }
  }

  FileView {
    path: root.overviewPath
    watchChanges: true
    printErrors: false
    onFileChanged: reload()
    onLoaded: root.parse(text())
    onLoadFailed: root.overview = null
  }

  // Keep the numbers fresh every few minutes even if the panel sits open.
  Timer {
    interval: 5 * 60 * 1000
    running: true
    repeat: true
    onTriggered: root.refreshData()
  }

  function refreshData() {
    if (root.bar) root.bar.run(root.updater)
  }

  function injectPanel() {
    var target = panelLoader.item
    if (!target) return
    if ("bar" in target) target.bar = root.bar
    if ("settings" in target) target.settings = root.settings
    if ("anchorItem" in target) target.anchorItem = button
    if ("hostWidget" in target) target.hostWidget = root
  }

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  onBarChanged: injectPanel()
  onSettingsChanged: injectPanel()

  Loader {
    id: panelLoader
    active: true
    source: Qt.resolvedUrl("Panel.qml")
    visible: false
    onLoaded: {
      root.injectPanel()
      Qt.callLater(root.injectPanel)
    }
  }

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: root.barText
    slotSize: -1
    tooltipText: "OpenRouter API cost — click for hourly/daily/weekly/monthly usage"
    onPressed: function(b) {
      if (b === Qt.LeftButton) {
        root.refreshData()
        root.togglePanel()
      }
    }
  }
}