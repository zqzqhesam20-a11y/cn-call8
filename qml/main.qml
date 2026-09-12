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
    property var transferDevices: []
    property bool transferPanelDismissed: false
    property string operationMessage: ""


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

                                    window.wirelessConnected = true
                                    window.usbReady = false

                                    if (window.wirelessConnected) {
                                        appController.useWirelessSource()
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

                                    window.usbReady = true
                                     window.wirelessConnected = false

                                    if (window.usbReady) {
                                        appController.useUsbSource()
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

                                        color: "#B9C3D2"
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
                                    appController.getADBDevices()
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
                                    appController.getADBDevices()
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
            appController.getADBDevices()
        }
    }


    // =============================================================
    // CONNECT TO EXISTING CONTROLLER SIGNALS
    // =============================================================

    Connections {

        target: appController

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

        function onTransferBatchChanged(devices) {
            window.transferDevices = devices
            if (devices && devices.length > 0)
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
                    text: window.operationBusy
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
                text: window.operationMessage
                color: "#B9C3D2"
                elide: Text.ElideRight
                maximumLineCount: 2
            }

            ListView {
                width: parent.width
                height: parent.height - 62
                clip: true
                spacing: 8
                model: window.transferDevices

                ScrollBar.vertical: ScrollBar {
                    policy: ScrollBar.AsNeeded
                }


                delegate: Rectangle {
                    width: ListView.view.width
                    height: 148
                    radius: 12
                    color: "#181F2B"
                    border.width: 1
                    border.color: modelData.status === "فشل"
                                  ? "#A83232"
                                  : modelData.status === "اكتمل"
                                    ? "#247A58"
                                    : "#29384A"

                    Column {
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 5

                        Text {
                            width: parent.width
                            text: modelData.model
                            color: "white"
                            font.pixelSize: 14
                            font.bold: true
                            elide: Text.ElideRight
                        }

                        Text {
                            width: parent.width
                            text: "Serial: " + modelData.serial
                            color: "#8F9CAF"
                            font.pixelSize: 11
                            elide: Text.ElideRight
                        }

                        Text {
                            width: parent.width
                            text: modelData.game
                            color: "#DCE4F0"
                            font.pixelSize: 11
                            elide: Text.ElideRight
                        }

                        Text {
                            width: parent.width
                            text: "الحالة: " + modelData.status
                            color: modelData.status === "فشل"
                                   ? "#FF7777"
                                   : modelData.status === "اكتمل"
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
                                visible: modelData.percent >= 0
                                width: parent.width
                                       * Math.max(0, Math.min(
                                           100, modelData.percent
                                       )) / 100
                                height: parent.height
                                radius: 4
                                color: "#00B8D9"
                            }
                        }

                        Text {
                            width: parent.width
                            text: modelData.percent >= 0
                                  ? modelData.percent + "%"
                                  : "جارٍ التنفيذ..."
                            color: "#DCE4F0"
                            font.pixelSize: 11
                        }

                        Text {
                            width: parent.width
                            text: modelData.operation
                                  + "  |  "
                                  + modelData.speed
                                  + "  |  ETA "
                                  + modelData.eta
                            color: "#AAB6C8"
                            font.pixelSize: 10
                            elide: Text.ElideRight
                        }

                        Text {
                            visible: modelData.error !== ""
                            width: parent.width
                            text: modelData.error
                            color: "#FF8C8C"
                            font.pixelSize: 10
                            elide: Text.ElideRight
                        }

                        Button {
                            visible: window.operationBusy
                                     && modelData.status !== "اكتمل"
                                     && modelData.status !== "فشل"
                                     && modelData.status !== "ملغي"
                            width: 88
                            height: 30
                            text: "إلغاء"
                            onClicked: appController.cancelDevice(
                                modelData.serial
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
                    width: ListView.view.width
                    text: modelData.model + " / " + modelData.serial
                    checked: window.selectedAdbSerials.indexOf(
                                 modelData.serial
                             ) !== -1
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
