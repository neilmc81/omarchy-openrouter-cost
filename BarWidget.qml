import QtQuick
import QtQuick.Shapes
import Quickshell
import Quickshell.Io
import qs.Ui
import qs.Commons

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

  // Bar label: the OpenRouter mark when working, ⚠ when no key is configured,
  // ! on error.
  readonly property string barText: root.barButtonText()

  function barButtonText() {
    var o = root.overview;
    if (o && o.error === "no-api-key") { return "⚠"; }
    if (o && o.error !== null && o.error !== "") { return "!"; }
    return "";
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
    iconComponent: root.barText === "" ? markComponent : null
    tooltipText: "OpenRouter API cost — click for hourly/daily/weekly/monthly usage"
    onPressed: function(b) {
      if (b === Qt.LeftButton) {
        root.refreshData()
        root.togglePanel()
      }
    }
  }

  Component {
    id: markComponent
    Item {
      BrandMark {
        anchors.centerIn: parent
        color: button.foreground
      }
    }
  }

  // OpenRouter brand mark drawn natively from its 24x24 SVG path, tinted with the
  // bar foreground (no Qt SVG/effect quirks in tiny bar slots).
  component BrandMark: Item {
    id: mark
    property real iconSize: Style.space(12)
    property color color: "white"
    width: iconSize
    height: iconSize
    implicitWidth: iconSize
    implicitHeight: iconSize
    Shape {
      width: 24
      height: 24
      scale: mark.iconSize / 24
      transformOrigin: Item.TopLeft
      preferredRendererType: Shape.CurveRenderer
      ShapePath {
        strokeWidth: -1
        fillColor: mark.color
        fillRule: ShapePath.WindingFill
        PathSvg { path: "M16.778 1.844v1.919q-.569-.026-1.138-.032-.708-.008-1.415.037c-1.93.126-4.023.728-6.149 2.237-2.911 2.066-2.731 1.95-4.14 2.75-.396.223-1.342.574-2.185.798-.841.225-1.753.333-1.751.333v4.229s.768.108 1.61.333c.842.224 1.789.575 2.185.799 1.41.798 1.228.683 4.14 2.75 2.126 1.509 4.22 2.11 6.148 2.236.88.058 1.716.041 2.555.005v1.918l7.222-4.168-7.222-4.17v2.176c-.86.038-1.611.065-2.278.021-1.364-.09-2.417-.357-3.979-1.465-2.244-1.593-2.866-2.027-3.68-2.508.889-.518 1.449-.906 3.822-2.59 1.56-1.109 2.614-1.377 3.978-1.466.667-.044 1.418-.017 2.278.02v2.176L24 6.014Z" }
      }
    }
  }
}
