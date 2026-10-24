import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "pages"

ApplicationWindow {

    id: window

    visible: true

    width: 1500
    height: 900

    minimumWidth: 1100
    minimumHeight: 700

    title: "كافيه نت هشام الريمي"

    color: "#070910"

    property string activePage: "الألعاب"

    property bool appUnlocked: false

    property bool wirelessConnected: true
    property bool usbReady: false
    property string activeSource: "WIRELESS"

    property int totalGames: 7
    property int transferPercent: 0
    property string transferSpeed: "0 B/s"
    property string transferEta: "00:00"

    // =============================================================
    // ANDROID / ADB DEVICE STATE
    // =============================================================

    property bool adbDeviceConnected: false
    property string adbDeviceText: "لا يوجد جهاز متصل"
    property var adbDevices: []
    property var selectedAdbSerials: []
    property bool operationBusy: false
    property bool operationPaused: false
    property var transferDevices: []
    property bool transferPanelDismissed: false

    // Stable model: update existing rows in place so progress ticks do not
    // reset ListView's model or jump the user's scroll position.
    ListModel {
        id: transferDevicesModel
    }

    function syncTransferDeviceModel(devices) {
        const incomingRows = devices || []
        const desiredSerials = []

        for (let i = 0; i < incomingRows.length; ++i) {
            const incoming = incomingRows[i]
            const serial = String(incoming.serial || "")
            if (serial.length === 0)
                continue

            desiredSerials.push(serial)
            const rowData = {
                serial: serial,
                deviceModel: String(incoming.model || "Android"),
                game: String(incoming.game || ""),
                kind: String(incoming.kind || ""),
                status: String(incoming.status || "انتظار"),
                percent: Number(incoming.percent === undefined ? 0 : incoming.percent),
                operation: String(incoming.operation || ""),
                speed: String(incoming.speed || "--"),
                eta: String(incoming.eta || "--"),
                error: String(incoming.error || ""),
                cancelled: Boolean(incoming.cancelled)
            }

            let rowIndex = -1
            for (let j = 0; j < transferDevicesModel.count; ++j) {
                if (transferDevicesModel.get(j).serial === serial) {
                    rowIndex = j
                    break
                }
            }

            if (rowIndex < 0) {
                transferDevicesModel.append(rowData)
            } else {
                const roleNames = Object.keys(rowData)
                const existingRow = transferDevicesModel.get(rowIndex)
                for (let k = 0; k < roleNames.length; ++k) {
                    const roleName = roleNames[k]
                    if (existingRow[roleName] !== rowData[roleName]) {
                        transferDevicesModel.setProperty(
                            rowIndex, roleName, rowData[roleName]
                        )
                    }
                }
            }
        }

        // Remove only devices that are no longer in the controller's snapshot.
        // Ordinary percentage/speed updates never clear or replace the model.
        for (let i = transferDevicesModel.count - 1; i >= 0; --i) {
            const serial = transferDevicesModel.get(i).serial
            if (desiredSerials.indexOf(serial) < 0)
                transferDevicesModel.remove(i)
        }
    }
    property string operationMessage: ""
    property string deviceCopyHelpTitle: "إرشادات إصلاح النسخ"
    property string deviceCopyHelpText: ""

    property var androidDataFallbackQueue: []
    property bool androidDataFallbackDialogActive: false
    property string androidDataFallbackSerial: ""
    property string androidDataFallbackGame: ""
    property string androidDataFallbackDestination: ""
    property string androidDataFallbackReason: ""

    function queueAndroidDataFallback(serial, gameName, destination, reason) {
        const queue = window.androidDataFallbackQueue.slice()
        queue.push({
            serial: String(serial || ""),
            gameName: String(gameName || "اللعبة"),
            destination: String(destination || "/sdcard/"),
            reason: String(reason || "")
        })
        window.androidDataFallbackQueue = queue
        window.openNextAndroidDataFallback()
    }

    function openNextAndroidDataFallback() {
        if (window.androidDataFallbackDialogActive
                || window.androidDataFallbackQueue.length === 0)
            return

        const queue = window.androidDataFallbackQueue.slice()
        const next = queue.shift()
        window.androidDataFallbackQueue = queue
        window.androidDataFallbackSerial = next.serial
        window.androidDataFallbackGame = next.gameName
        window.androidDataFallbackDestination = next.destination
        window.androidDataFallbackReason = next.reason
        window.androidDataFallbackDialogActive = true
        androidDataFallbackDialog.open()
    }

    function finishAndroidDataFallback(useRoot) {
        const serial = window.androidDataFallbackSerial
        if (!serial)
            return

        if (useRoot) {
            if (!appController.copyToDeviceRoot(serial))
                appController.declineRootFallback(serial)
        } else {
            appController.declineRootFallback(serial)
        }

        window.androidDataFallbackDialogActive = false
        androidDataFallbackDialog.close()
        window.androidDataFallbackSerial = ""
        window.androidDataFallbackGame = ""
        window.androidDataFallbackDestination = ""
        window.androidDataFallbackReason = ""
        Qt.callLater(window.openNextAndroidDataFallback)
    }


    // =============================================================
    // MAIN
    // =============================================================

    Row {

        anchors.fill: parent

        spacing: 0


        // =========================================================
        // SIDEBAR
        // =========================================================

        Rectangle {

            width: 240

            height: parent.height

            color: "#0B0E16"


            Column {

                anchors.fill: parent

                anchors.margins: 18

                spacing: 10


                Rectangle {

                    width: parent.width

                    height: 75

                    color: "transparent"


                    Column {

                        anchors.left: parent.left

                        anchors.verticalCenter: parent.verticalCenter

                        spacing: 2


                        Text {

                            text: "كافيه نت"

                            color: "#00D9FF"

                            font.pixelSize: 27

                            font.bold: true
                        }


                        Text {

                            text: "هشام الريمي"

                            color: "#737B8F"

                            font.pixelSize: 13

                            font.bold: true
                        }

                    }

                }


                Rectangle {

                    width: parent.width

                    height: 1

                    color: "#202532"

                }


                Item {

                    width: 1

                    height: 8

                }


                Repeater {

                    model: [

                        { title: "🎮  الألعاب", page: "الألعاب" },

                        { title: "📂  نقل الملفات", page: "نقل الملفات" },

                        { title: "📦  التثبيت", page: "التثبيت" },

                        { title: "📜  سجل النقل", page: "سجل النقل" },

                        { title: "💾  التخزين", page: "التخزين" },

                        { title: "⚙  الإعدادات", page: "الإعدادات" }

                    ]


                    delegate: Rectangle {

                        width: parent.width

                        height: 48

                        radius: 10

                        color: window.activePage === modelData.page
                               ? "#102C38"
                               : "transparent"


                        Rectangle {

                            visible: window.activePage === modelData.page

                            width: 3

                            height: 28

                            radius: 2

                            anchors.left: parent.left

                            anchors.verticalCenter: parent.verticalCenter

                            color: "#00D9FF"

                        }


                        Text {

                            anchors.fill: parent

                            anchors.leftMargin: 18

                            verticalAlignment: Text.AlignVCenter

                            text: modelData.title

                            color: window.activePage === modelData.page
                                   ? "#FFFFFF"
                                   : "#9AA2B3"

                            font.pixelSize: 15

                            font.bold: window.activePage === modelData.page

                        }


                        MouseArea {

                            anchors.fill: parent

                            cursorShape: Qt.PointingHandCursor

                            onClicked: {

                                window.activePage = modelData.page

                            }

                        }

                    }

                }


                Item {

                    width: 1

                    height: 6

                }


                // SYSTEM STATUS

                Rectangle {

                    width: parent.width

                    height: 112

                    radius: 14

                    color: "#0F141E"

                    border.width: 1

                    border.color: "#1E2634"


                    Column {

                        anchors.fill: parent

                        anchors.margins: 14

                        spacing: 9


                        Text {

                            text: "حالة النظام"

                            color: "#7E879A"

                            font.pixelSize: 12

                        }


                        Row {

                            spacing: 8


                            Rectangle {

                                width: 9

                                height: 9

                                radius: 5

                                color: "#27D17F"

                                anchors.verticalCenter: parent.verticalCenter

                            }


                            Text {

                                text: "النظام يعمل"

                                color: "#D9E0EC"

                                font.pixelSize: 13

                            }

                        }


                        Row {

                            spacing: 8


                            Text {

                                text: "الألعاب"

                                color: "#687285"

                                font.pixelSize: 11

                            }


                            Text {

                                text: window.totalGames

                                color: "#00D9FF"

                                font.pixelSize: 11

                                font.bold: true

                            }

                        }

                    }

                }


                Item {

                    width: 1

                    height: 1

                }


                Text {

                    width: parent.width

                    text: "هشام الريمي"

                    color: "#3F4757"

                    horizontalAlignment: Text.AlignHCenter

                    font.pixelSize: 11

                }

            }

        }


        // =========================================================
        // MAIN AREA
        // =========================================================

        Rectangle {

            width: parent.width - 240

            height: parent.height

            color: "#070910"


            Column {

                anchors.fill: parent

                spacing: 0


                // =================================================
                // HEADER
                // =================================================

                Rectangle {

                    width: parent.width

                    height: 108

                    color: "#0B0E16"


                    RowLayout {

                        anchors.fill: parent

                        anchors.leftMargin: 30

                        anchors.rightMargin: 30

                        spacing: 14


                        ColumnLayout {

                            Layout.fillWidth: true

                            spacing: 3


                            Text {

                                text: window.activePage

                                color: "#FFFFFF"

                                font.pixelSize: 28

                                font.bold: true

                            }


                            Text {

                                text: "إدارة ونقل ألعاب الأجهزة بسهولة وسرعة"

                                color: "#737C90"

                                font.pixelSize: 13

                            }

                        }


                        // =================================================
                        // TRANSFER MINI STATUS
                        // =================================================

                        Rectangle {

                            Layout.preferredWidth: 175

                            Layout.preferredHeight: 58

                            radius: 12

                            color: "#0E121A"

                            border.width: 1

                            border.color: "#202938"


                            Column {

                                anchors.fill: parent

                                anchors.margins: 10

                                spacing: 3


                                Text {

                                    text: "النقل الحالي"

                                    color: "#697386"

                                    font.pixelSize: 10

                                }


                                Row {

                                    spacing: 8


                                    Text {

                                        text: window.transferPercent + "%"

                                        color: "#FFFFFF"

                                        font.pixelSize: 15

                                        font.bold: true

                                    }


                                    Text {

                                        text: window.transferSpeed

                                        color: "#00D9FF"

                                        font.pixelSize: 11

                                    }

                                }

                            }

                        }


                        // =================================================
                        // WIRELESS
                        // =================================================

                        Rectangle {

                            Layout.preferredWidth: 155

                            Layout.preferredHeight: 58

                            radius: 12

                            color: window.wirelessConnected
                                   ? "#0E171C"
                                   : "#151015"

                            border.width: 1

                            border.color: window.wirelessConnected
                                           ? "#193642"
                                           : "#3A2025"


                            Column {

                                anchors.fill: parent

                                anchors.margins: 10

                                spacing: 3


                                Text {

                                    text: "LAN"

                                    color: window.wirelessConnected
                                           ? "#00D9FF"
                                           : "#D96B76"

                                    font.pixelSize: 12

                                    font.bold: true

                                }


                                Row {

                                    spacing: 6


                                    Rectangle {

                                        width: 7

                                        height: 7

                                        radius: 4

                                        color: window.wirelessConnected
                                               ? "#27D17F"
                                               : "#D94D5B"

                                        anchors.verticalCenter: parent.verticalCenter

                                    }


                                    Text {

                                        text: window.wirelessConnected
                                              ? "متصل"
                                              : "غير متصل"

                                        color: "#B9C3D2"

                                        font.pixelSize: 11

                                    }

                                }

                            }


                            MouseArea {

                                anchors.fill: parent

                                cursorShape: Qt.PointingHandCursor

                                onClicked: {
                                    if (appController.useWirelessSource()) {
                                        window.wirelessConnected = true
                                        window.usbReady = false
                                        window.activeSource = "WIRELESS"
                                    }
                                }

                            }

                        }


                        // =================================================
                        // USB
                        // =================================================

                        Rectangle {

                            Layout.preferredWidth: 135

                            Layout.preferredHeight: 58

                            radius: 12

                            color: window.usbReady
                                   ? "#101820"
                                   : "#151015"

                            border.width: 1

                            border.color: window.usbReady
                                           ? "#243A43"
                                           : "#3A2025"


                            Column {

                                anchors.fill: parent

                                anchors.margins: 10

                                spacing: 3


                                Text {

                                    text: "HDD"

                                    color: "#FFFFFF"

                                    font.pixelSize: 12

                                    font.bold: true

                                }


                                Row {

                                    spacing: 6


                                    Rectangle {

                                        width: 7

                                        height: 7

                                        radius: 4

                                        color: window.usbReady
                                               ? "#27D17F"
                                               : "#D94D5B"

                                        anchors.verticalCenter: parent.verticalCenter

                                    }


                                    Text {

                                        text: window.usbReady
                                              ? "متصل"
                                              : "غير متصل"

                                        color: "#B9C3D2"

                                        font.pixelSize: 11

                                    }

                                }

                            }


                            MouseArea {

                                anchors.fill: parent

                                cursorShape: Qt.PointingHandCursor

                                onClicked: {
                                    if (appController.useUsbSource()) {
                                        window.usbReady = true
                                        window.wirelessConnected = false
                                        window.activeSource = "USB"
                                    }
                                }

                            }

                        }



                        // =================================================
                        // ANDROID DEVICES / ADB
                        // =================================================

                        Rectangle {

                            Layout.preferredWidth: 190
                            Layout.preferredHeight: 58

                            radius: 12

                            color: window.adbDeviceConnected
                                   ? "#0E171C"
                                   : "#151015"

                            border.width: 1

                            border.color: window.adbDeviceConnected
                                           ? "#193642"
                                           : "#3A2025"

                            Column {

                                anchors.fill: parent
                                anchors.margins: 10
                                spacing: 3

                                Text {

                                    text: "📱 الأجهزة"

                                    color: window.adbDeviceConnected
                                           ? "#00D9FF"
                                           : "#D96B76"

                                    font.pixelSize: 12
                                    font.bold: true

                                }

                                Row {

                                    spacing: 6

                                    Rectangle {

                                        width: 7
                                        height: 7
                                        radius: 4

                                        color: window.adbDeviceConnected
                                               ? "#27D17F"
                                               : "#D94D5B"

                                        anchors.verticalCenter: parent.verticalCenter

                                    }

                                    Text {

                                        text: window.adbDeviceConnected
                                              ? window.adbDeviceText
                                              : "لا يوجد جهاز متصل"

                                        color: "#FFFFFF"
                                        font.pixelSize: 10

                                        elide: Text.ElideRight
                                        maximumLineCount: 1

                                    }

                                }

                            }

                            MouseArea {

                                anchors.fill: parent

                                cursorShape: Qt.PointingHandCursor

                                onClicked: {
                                    appController.refreshADBDevices()
                                    adbDevicePopup.open()
                                }

                            }

                        }


                        // =================================================
                        // REFRESH
                        // =================================================

                        Rectangle {

                            Layout.preferredWidth: 48

                            Layout.preferredHeight: 48

                            radius: 12

                            color: "#10141D"

                            border.width: 1

                            border.color: "#242B39"


                            Text {

                                anchors.centerIn: parent

                                text: "↻"

                                color: "#AAB3C3"

                                font.pixelSize: 23

                            }


                            MouseArea {

                                anchors.fill: parent

                                cursorShape: Qt.PointingHandCursor

                                onClicked: {

                                    console.log("REFRESH")
                                    appController.refreshADBDevices()
                                    adbDevicePopup.open()

                                }

                            }

                        }


                        // SETTINGS

                        Rectangle {

                            Layout.preferredWidth: 48

                            Layout.preferredHeight: 48

                            radius: 12

                            color: "#10141D"

                            border.width: 1

                            border.color: "#242B39"


                            Text {

                                anchors.centerIn: parent

                                text: "⚙"

                                color: "#AAB3C3"

                                font.pixelSize: 19

                            }


                            MouseArea {

                                anchors.fill: parent

                                cursorShape: Qt.PointingHandCursor

                                onClicked: {

                                    window.activePage = "الإعدادات"

                                }

                            }

                        }

                    }

                }


                // =================================================
                // CONTENT
                // =================================================

                Item {

                    width: parent.width

                    height: parent.height - 108


                    Dashboard {

                        anchors.fill: parent

                    }

                }

            }

        }

    }


    Component.onCompleted: {
        if (appController && appController.getADBDevices) {
            appController.refreshADBDevices()
        }
    }


    // =============================================================
    // CONNECT TO EXISTING CONTROLLER SIGNALS
    // =============================================================

    Connections {

        target: appController

        function onAndroidDataFallbackRequested(serial, gameName, destination, reason) {
            window.queueAndroidDataFallback(serial, gameName, destination, reason)
        }

        function onTransferPercentChanged(percent) {

            window.transferPercent = percent

        }

        function onTransferSpeedChanged(speed) {

            window.transferSpeed = speed

        }

        function onTransferEtaChanged(eta) {

            window.transferEta = eta

        }

        function onTransferFinished(success, message) {

            if (success) {

                window.transferPercent = 100

            }

            else {

                window.transferPercent = 0

            }

        }

        function onOperationStateChanged(state) {
            window.operationBusy = state !== "IDLE"
        }

        function onTransferPausedChanged(paused) {
            window.operationPaused = paused
        }

        function onTransferBatchChanged(devices) {
            window.transferDevices = devices || []
            window.syncTransferDeviceModel(window.transferDevices)
            if (window.transferDevices.length > 0)
                window.transferPanelDismissed = false
        }

        function onOperationFinished(message) {
            window.operationMessage = message
        }

        function onOperationRejected(message) {
            window.operationMessage = message
        }

        function onMessageChanged(message) {
            window.operationMessage = message
        }

        function onAdbDevicesChanged(devices) {
            console.log("ADB DEVICES FROM PYTHON:", devices)

            if (!devices || devices.length === 0) {

                window.adbDeviceConnected = false
                window.adbDeviceText = "لا يوجد جهاز متصل"
                window.adbDevices = []
                window.selectedAdbSerials = []

                return
            }

            window.adbDeviceConnected = true
            window.adbDevices = devices
            window.selectedAdbSerials = window.selectedAdbSerials.filter(
                function(serial) {
                    return devices.some(function(device) {
                        return device.serial === serial
                    })
                }
            )
            window.adbDeviceText = devices.length
                    + " جهاز متصل - "
                    + window.selectedAdbSerials.length
                    + " محدد"

        }

    }

    Rectangle {
        id: transferPanel

        visible: window.transferDevices.length > 0 && !window.transferPanelDismissed
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.rightMargin: 24
        anchors.bottomMargin: 24
        width: 500
        height: Math.min(parent.height - 48, 620)
        radius: 16
        color: "#111722"
        border.width: 1
        border.color: window.operationBusy ? "#00AFCF" : "#2A3445"
        z: 20

        Column {
            anchors.fill: parent
            anchors.margins: 16
            spacing: 10

            RowLayout {
                width: parent.width
                height: 38
                spacing: 8

                Text {
                    Layout.fillWidth: true
                    text: window.operationPaused
                          ? "النقل متوقف مؤقتًا"
                          : window.operationBusy
                            ? "العملية قيد التنفيذ"
                            : "نتيجة العملية"
                    color: "#00D9FF"
                    font.pixelSize: 16
                    font.bold: true
                    elide: Text.ElideRight
                }

                Row {
                    Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
                    spacing: 8

                    Button {
                        width: 82
                        height: 34
                        visible: window.operationBusy && !window.operationPaused
                        text: "إيقاف مؤقت"
                        onClicked: appController.pauseTransfer()

                        background: Rectangle {
                            radius: 10
                            color: parent.pressed ? "#59451F"
                                   : parent.hovered ? "#3C321F"
                                   : "#282519"
                            border.width: 1
                            border.color: "#80662B"
                        }

                        contentItem: Text {
                            text: parent.text
                            color: "#FFE19A"
                            font.pixelSize: 11
                            font.bold: true
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }

                    Button {
                        width: 82
                        height: 34
                        visible: window.operationBusy && window.operationPaused
                        text: "استئناف"
                        onClicked: appController.resumeTransfer()

                        background: Rectangle {
                            radius: 10
                            color: parent.pressed ? "#1C6B4A"
                                   : parent.hovered ? "#184D3A"
                                   : "#153629"
                            border.width: 1
                            border.color: "#287A58"
                        }

                        contentItem: Text {
                            text: parent.text
                            color: "#9BF0C5"
                            font.pixelSize: 11
                            font.bold: true
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }

                    Button {
                        width: 104
                        height: 34
                        visible: window.operationBusy
                        text: "إلغاء الكل"
                        onClicked: appController.cancelTransfer()

                        background: Rectangle {
                            radius: 10
                            color: parent.pressed ? "#7A2734"
                                   : parent.hovered ? "#542630"
                                   : "#2C1B24"
                            border.width: 1
                            border.color: "#944052"
                        }

                        contentItem: Text {
                            text: parent.text
                            color: "#FFC0C7"
                            font.pixelSize: 12
                            font.bold: true
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }

                    Button {
                        width: 34
                        height: 34
                        text: "✕"
                        onClicked: window.transferPanelDismissed = true

                        background: Rectangle {
                            radius: 10
                            color: parent.pressed ? "#343C4B"
                                   : parent.hovered ? "#252E3D"
                                   : "#1A2230"
                            border.width: 1
                            border.color: "#3A4659"
                        }

                        contentItem: Text {
                            text: parent.text
                            color: "#C6CEDB"
                            font.pixelSize: 15
                            font.bold: true
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }
                }
            }

            Text {
                width: parent.width
                height: 34
                text: window.operationMessage
                color: "#B9C3D2"
                wrapMode: Text.Wrap
                maximumLineCount: 2
                elide: Text.ElideRight
                verticalAlignment: Text.AlignVCenter
            }

            ListView {
                id: transferListView
                width: parent.width
                height: parent.height - 104
                clip: true
                spacing: 8
                model: transferDevicesModel

                ScrollBar.vertical: ScrollBar {
                    policy: ScrollBar.AsNeeded
                }


                delegate: Rectangle {
                    width: ListView.view.width
                    height: 244
                    radius: 12
                    color: "#181F2B"
                    border.width: 1
                    border.color: status === "فشل"
                                  ? "#A83232"
                                  : status === "اكتمل"
                                    ? "#247A58"
                                    : "#29384A"

                    Column {
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 5

                        Text {
                            width: parent.width
                            text: deviceModel
                            color: "white"
                            font.pixelSize: 14
                            font.bold: true
                            elide: Text.ElideRight
                        }

                        Text {
                            width: parent.width
                            text: "Serial: " + serial
                            color: "#8F9CAF"
                            font.pixelSize: 11
                            elide: Text.ElideRight
                        }

                        Text {
                            width: parent.width
                            text: game
                            color: "#DCE4F0"
                            font.pixelSize: 11
                            elide: Text.ElideRight
                        }

                        Text {
                            width: parent.width
                            text: "الحالة: " + status
                            color: status === "فشل"
                                   ? "#FF7777"
                                   : status === "اكتمل"
                                     ? "#42D995"
                                     : "#00D9FF"
                            font.pixelSize: 12
                            font.bold: true
                        }

                        Rectangle {
                            width: parent.width
                            height: 7
                            radius: 4
                            color: "#252C3A"

                            Rectangle {
                                visible: percent >= 0
                                width: parent.width
                                       * Math.max(0, Math.min(
                                           100, percent
                                       )) / 100
                                height: parent.height
                                radius: 4
                                color: "#00B8D9"
                            }
                        }

                        Text {
                            width: parent.width
                            text: percent >= 0
                                  ? percent + "%"
                                  : "جارٍ التنفيذ..."
                            color: "#DCE4F0"
                            font.pixelSize: 11
                        }

                        Text {
                            width: parent.width
                            text: operation
                                  + "  |  "
                                  + speed
                                  + "  |  ETA "
                                  + eta
                            color: "#AAB6C8"
                            font.pixelSize: 10
                            elide: Text.ElideRight
                        }

                        Text {
                            visible: error !== ""
                            width: parent.width
                            text: error
                            color: "#FF8C8C"
                            font.pixelSize: 10
                            wrapMode: Text.Wrap
                            maximumLineCount: 2
                            elide: Text.ElideRight
                        }

                        Button {
                            visible: status === "فشل"
                                     && kind === "copy"
                            width: 144
                            height: 28
                            text: "إرشادات الإصلاح"
                            onClicked: {
                                window.deviceCopyHelpTitle =
                                    "إصلاح النسخ — " + deviceModel
                                window.deviceCopyHelpText =
                                    appController.deviceCopyHelp(serial)
                                deviceCopyHelpDialog.open()
                            }

                            background: Rectangle {
                                radius: 8
                                color: parent.pressed ? "#194D5B"
                                       : parent.hovered ? "#153846"
                                       : "#122B35"
                                border.width: 1
                                border.color: "#26768A"
                            }

                            contentItem: Text {
                                text: parent.text
                                color: "#9CEBFA"
                                font.pixelSize: 11
                                font.bold: true
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                        }

                        Button {
                            visible: window.operationBusy
                                     && status !== "اكتمل"
                                     && status !== "فشل"
                                     && status !== "ملغي"
                            width: 88
                            height: 30
                            text: "إلغاء"
                            onClicked: appController.cancelDevice(
                                serial
                            )

                            background: Rectangle {
                                radius: 9
                                color: parent.pressed ? "#702630"
                                       : parent.hovered ? "#51242D"
                                       : "#281B22"
                                border.width: 1
                                border.color: "#8D3A49"
                            }

                            contentItem: Text {
                                text: parent.text
                                color: "#FFB6BF"
                                font.pixelSize: 11
                                font.bold: true
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                        }
                    }
                }
            }
        }
    }

    Dialog {
        id: deviceCopyHelpDialog
        modal: true
        focus: true
        title: window.deviceCopyHelpTitle
        width: Math.min(660, window.width - 40)
        height: Math.min(540, window.height - 40)
        x: Math.max(20, (window.width - width) / 2)
        y: Math.max(20, (window.height - height) / 2)
        standardButtons: Dialog.Ok

        background: Rectangle {
            color: "#111722"
            radius: 14
            border.width: 1
            border.color: "#26768A"
        }

        contentItem: ScrollView {
            clip: true

            Text {
                width: deviceCopyHelpDialog.width - 72
                text: window.deviceCopyHelpText
                color: "#DCE4F0"
                font.pixelSize: 13
                wrapMode: Text.Wrap
                padding: 10
                textFormat: Text.PlainText
            }
        }
    }

    Dialog {
        id: androidDataFallbackDialog
        modal: true
        focus: true
        closePolicy: Popup.NoAutoClose
        title: "تعذر النسخ إلى Android/data"
        width: Math.min(640, window.width - 40)
        height: Math.min(460, window.height - 40)
        x: Math.max(20, (window.width - width) / 2)
        y: Math.max(20, (window.height - height) / 2)

        background: Rectangle {
            color: "#111722"
            radius: 14
            border.width: 1
            border.color: "#C18A39"
        }

        contentItem: ScrollView {
            clip: true
            Column {
                width: androidDataFallbackDialog.width - 48
                spacing: 12

                Text {
                    width: parent.width
                    text: "رفض الهاتف " + window.androidDataFallbackSerial
                          + " الكتابة إلى Android/data أثناء نسخ "
                          + window.androidDataFallbackGame + "."
                    color: "#DCE4F0"
                    wrapMode: Text.Wrap
                    font.pixelSize: 14
                }

                Text {
                    width: parent.width
                    text: "هل تريد إعادة النسخ إلى مجلد مستقل في جذر الذاكرة الداخلية بدلًا من ذلك؟"
                    color: "#DCE4F0"
                    wrapMode: Text.Wrap
                    font.pixelSize: 13
                }

                Rectangle {
                    width: parent.width
                    height: 48
                    radius: 8
                    color: "#1A2533"
                    border.width: 1
                    border.color: "#5B6E86"

                    Text {
                        anchors.fill: parent
                        anchors.margins: 10
                        verticalAlignment: Text.AlignVCenter
                        text: window.androidDataFallbackDestination
                        color: "#9CEBFA"
                        font.pixelSize: 13
                        elide: Text.ElideMiddle
                    }
                }

                Text {
                    width: parent.width
                    text: window.androidDataFallbackReason
                    color: "#AAB6C8"
                    wrapMode: Text.Wrap
                    font.pixelSize: 11
                    textFormat: Text.PlainText
                }
            }
        }

        footer: RowLayout {
            width: androidDataFallbackDialog.width - 24
            spacing: 12

            Button {
                text: "نسخ إلى الجذر"
                Layout.alignment: Qt.AlignRight
                onClicked: window.finishAndroidDataFallback(true)
            }

            Button {
                text: "إلغاء"
                onClicked: window.finishAndroidDataFallback(false)
            }
        }
    }

    Popup {
        id: adbDevicePopup

        x: 250
        y: 95
        width: 390
        height: Math.min(window.height - 130, 460)
        modal: true
        focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

        background: Rectangle {
            color: "#111722"
            radius: 14
            border.width: 1
            border.color: "#26394A"
        }

        contentItem: Column {
            spacing: 10
            padding: 16

            Text {
                text: "الأجهزة المتصلة"
                color: "#00D9FF"
                font.pixelSize: 16
                font.bold: true
            }

            ListView {
                width: parent.width
                height: 300
                clip: true
                model: window.adbDevices

                delegate: CheckBox {
                    id: deviceSelectionCheckBox
                    width: ListView.view.width
                    height: 42
                    padding: 8
                    spacing: 8
                    text: modelData.model + " / " + modelData.serial
                    checked: window.selectedAdbSerials.indexOf(
                                 modelData.serial
                             ) !== -1

                    // Explicit high-contrast text and selection styling:
                    // the selected device remains readable against the popup.
                    indicator: Rectangle {
                        implicitWidth: 20
                        implicitHeight: 20
                        x: deviceSelectionCheckBox.leftPadding
                        y: deviceSelectionCheckBox.height / 2 - height / 2
                        radius: 5
                        color: deviceSelectionCheckBox.checked
                               ? "#00D9FF"
                               : "#0B111A"
                        border.width: 1
                        border.color: deviceSelectionCheckBox.checked
                                      ? "#00D9FF"
                                      : "#65748A"

                        Text {
                            anchors.centerIn: parent
                            visible: deviceSelectionCheckBox.checked
                            text: "✓"
                            color: "#071019"
                            font.pixelSize: 14
                            font.bold: true
                        }
                    }

                    contentItem: Text {
                        text: deviceSelectionCheckBox.text
                        color: deviceSelectionCheckBox.checked
                               ? "#FFFFFF"
                               : "#DCE4F0"
                        font.pixelSize: 12
                        font.bold: deviceSelectionCheckBox.checked
                        verticalAlignment: Text.AlignVCenter
                        leftPadding: deviceSelectionCheckBox.indicator.width
                                     + deviceSelectionCheckBox.spacing
                        rightPadding: 8
                        elide: Text.ElideRight
                    }

                    background: Rectangle {
                        radius: 8
                        color: deviceSelectionCheckBox.checked
                               ? "#153845"
                               : deviceSelectionCheckBox.hovered
                                 ? "#1A2432"
                                 : "#141B27"
                        border.width: 1
                        border.color: deviceSelectionCheckBox.checked
                                      ? "#00D9FF"
                                      : "#2A3546"
                    }

                    onClicked: {
                        var selected = window.selectedAdbSerials.slice()
                        var index = selected.indexOf(modelData.serial)
                        if (checked && index === -1)
                            selected.push(modelData.serial)
                        else if (!checked && index !== -1)
                            selected.splice(index, 1)
                        window.selectedAdbSerials = selected
                        appController.setADBDeviceSelection(selected)
                        window.adbDeviceText = window.adbDevices.length
                                + " جهاز متصل - "
                                + selected.length
                                + " محدد"
                    }
                }
            }

            Row {
                spacing: 8

                Button {
                    text: "تحديد الكل"
                    onClicked: {
                        var selected = []
                        for (var i = 0; i < window.adbDevices.length; i++)
                            selected.push(window.adbDevices[i].serial)
                        window.selectedAdbSerials = selected
                        appController.setADBDeviceSelection(selected)
                        window.adbDeviceText = window.adbDevices.length
                                + " جهاز متصل - "
                                + selected.length
                                + " محدد"
                    }
                }

                Button {
                    text: "مسح الكل"
                    onClicked: {
                        window.selectedAdbSerials = []
                        appController.setADBDeviceSelection([])
                        window.adbDeviceText = window.adbDevices.length
                                + " جهاز متصل - 0 محدد"
                    }
                }

                Text {
                    text: window.selectedAdbSerials.length + " أجهزة محددة"
                    color: "#B9C3D2"
                    anchors.verticalCenter: parent.verticalCenter
                }
            }
        }
    }



    Dialog {
        id: startupPasswordDialog

        modal: true
        closePolicy: Popup.NoAutoClose
        visible: true

        width: 380
        height: 230

        anchors.centerIn: parent

        standardButtons: Dialog.NoButton

        background: Rectangle {
            radius: 15
            color: "#111722"
            border.width: 1
            border.color: "#2A3445"
        }

        Column {
            anchors.fill: parent
            anchors.margins: 25
            spacing: 15

            Text {
                width: parent.width
                text: "ادخل كلمة السر"
                color: "white"
                font.pixelSize: 18
                horizontalAlignment: Text.AlignHCenter
            }

            TextField {
                id: startupPasswordField

                width: parent.width
                height: 42

                echoMode: TextInput.Password

                placeholderText: "كلمة السر"

                horizontalAlignment: TextInput.AlignHCenter
            }

            Text {
                id: startupPasswordError

                width: parent.width

                text: "كلمة المرور غير صحيحة"

                color: "#FF5555"

                visible: false

                horizontalAlignment: Text.AlignHCenter
            }

            Button {
                width: parent.width
                height: 40

                text: "دخول"

                onClicked: {

                    if (startupPasswordField.text === "يخىحمشغصهفاةث") {

                        startupPasswordError.visible = false
                        startupPasswordDialog.close()

                    } else {

                        startupPasswordError.visible = true
                        startupPasswordField.selectAll()
                        startupPasswordField.forceActiveFocus()

                    }
                }
            }
        }
    }

}
