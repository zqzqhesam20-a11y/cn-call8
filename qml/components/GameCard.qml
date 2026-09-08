import QtQuick
import QtQuick.Controls

Item {
    id: root

    property string gameName: ""
    property string imageSource: ""
    property string gameColor: "#00D9FF"


    width: 245
    height: 310

    Rectangle {
        id: card

        anchors.fill: parent

        radius: 22

        color: "#151927"

        border.width: mouseArea.containsMouse ? 2 : 1

        border.color: mouseArea.containsMouse
                      ? root.gameColor
                      : "#252A38"

        clip: true

        Image {
            anchors.fill: parent

            source: root.imageSource

            fillMode: Image.PreserveAspectCrop

            asynchronous: true
            cache: true

            scale: mouseArea.containsMouse ? 1.04 : 1.0

            Behavior on scale {
                NumberAnimation {
                    duration: 250
                    easing.type: Easing.OutCubic
                }
            }
        }

        Rectangle {
            anchors.fill: parent

            gradient: Gradient {
                GradientStop {
                    position: 0.0
                    color: "#00000000"
                }

                GradientStop {
                    position: 0.55
                    color: "#22000000"
                }

                GradientStop {
                    position: 1.0
                    color: "#E8000000"
                }
            }
        }

        Text {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom

            anchors.leftMargin: 18
            anchors.rightMargin: 18
            anchors.bottomMargin: 16

            text: root.gameName

            color: "white"

            font.pixelSize: 20
            font.bold: true

            opacity: mouseArea.containsMouse ? 0 : 1

            Behavior on opacity {
                NumberAnimation {
                    duration: 130
                }
            }
        }

        Rectangle {
            anchors.fill: parent

            radius: 22

            color: "#E6111522"

            opacity: mouseArea.containsMouse ? 1 : 0

            Behavior on opacity {
                NumberAnimation {
                    duration: 180
                }
            }

            Column {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter

                anchors.margins: 20

                spacing: 8

                Text {
                    text: root.gameName

                    color: "white"

                    font.pixelSize: 22
                    font.bold: true
                }

                Rectangle {
                    width: 45
                    height: 3

                    radius: 2

                    color: root.gameColor
                }

                Text {
                    text: "📂 المصدر: العابي/" + root.gameName

                    color: "#D0D5E0"

                    font.pixelSize: 12

                    elide: Text.ElideRight

                    width: parent.width
                }

                Text {
                    text: "💾 الحجم: -- GB"

                    color: root.gameColor

                    font.pixelSize: 13
                    font.bold: true
                }

                Text {
                    text: "📦 الوجهة: قابلة للتعديل"

                    color: "#B8BDCA"

                    font.pixelSize: 12
                }

                Column {
                    width: parent.width
                    spacing: 7

                    Row {
                        width: parent.width
                        spacing: 7

                        Button {
                            width: (parent.width - 7) / 2
                            height: 36


                            onClicked: {
                                appController.installGame(
                                    root.gameName
                                )
                            }

                            background: Rectangle {
                                radius: 9
                                color: "#252C3A"
                                border.width: 1
                                border.color: "#3A4355"
                            }

                            contentItem: Text {
                                text: "تثبيت"
                                color: "white"
                                font.pixelSize: 13
                                font.bold: true
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                        }

                        Button {
                            width: (parent.width - 7) / 2
                            height: 36


                            onClicked: {
                                appController.launchGame(
                                    root.gameName
                                )
                            }

                            background: Rectangle {
                                radius: 9
                                color: enabled
                                       ? "#173A32"
                                       : "#3A4050"
                                border.width: 1
                                border.color: "#2B6656"
                            }

                            contentItem: Text {
                                text: "فتح اللعبة"
                                color: "white"
                                font.pixelSize: 12
                                font.bold: true
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                        }
                    }

                    Button {
                        width: parent.width
                        height: 36


                        onClicked: {
                            passwordField.text = ""
                            passwordError.visible = false
                            appController.copyGame(
                                root.gameName
                            )
                        }

                        background: Rectangle {
                            radius: 9
                            color: enabled
                                   ? root.gameColor
                                   : "#3A4050"
                        }

                        contentItem: Text {
                            text: "نسخ"
                            color: "white"
                            font.pixelSize: 13
                            font.bold: true
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }

                    Button {
                        width: 40
                        height: 36

                        background: Rectangle {
                            radius: 9
                            color: "#252C3A"
                        }

                        contentItem: Text {
                            text: "⚙"
                            color: "white"
                            font.pixelSize: 15
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }
                }
            }
        }

        Dialog {
            id: copyPasswordDialog

            modal: true
            title: "تأكيد النسخ"

            width: 390
            height: 250

            anchors.centerIn: parent

            standardButtons: Dialog.NoButton

            background: Rectangle {
                radius: 14
                color: "#111722"
                border.width: 1
                border.color: "#2A3445"
            }

            Column {
                anchors.fill: parent
                anchors.margins: 22
                spacing: 12

                Text {
                    width: parent.width
                    text: "أدخل كلمة السر لبدء نسخ اللعبة"
                    color: "white"
                    font.pixelSize: 15
                    font.bold: true
                    horizontalAlignment: Text.AlignHCenter
                }

                TextField {
                    id: passwordField

                    width: parent.width
                    height: 42

                    echoMode: TextInput.Password

                    placeholderText: "كلمة السر"

                    horizontalAlignment: TextInput.AlignHCenter

                    color: "white"

                    background: Rectangle {
                        radius: 9
                        color: "#1B2230"
                        border.width: 1
                        border.color: "#344055"
                    }

                    onAccepted: {
                        passwordCheckButton.clicked()
                    }
                }

                Text {
                    id: passwordError

                    width: parent.width

                    text: "كلمة السر غير صحيحة"

                    color: "#FF5C5C"

                    font.pixelSize: 12
                    horizontalAlignment: Text.AlignHCenter

                    visible: false
                }

                Row {
                    width: parent.width
                    spacing: 8

                    Button {
                        id: passwordCheckButton

                        width: (parent.width - 8) / 2
                        height: 38

                        onClicked: {
                            if (passwordField.text === "مثفسلخ") {

                                passwordError.visible = false
                                copyPasswordDialog.close()

                                appController.copyGame(
                                    root.gameName
                                )

                            } else {

                                passwordError.visible = true
                                passwordField.selectAll()
                                passwordField.forceActiveFocus()
                            }
                        }

                        background: Rectangle {
                            radius: 9
                            color: "#173A32"
                        }

                        contentItem: Text {
                            text: "تأكيد"
                            color: "white"
                            font.pixelSize: 13
                            font.bold: true
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }

                    Button {
                        width: (parent.width - 8) / 2
                        height: 38

                        onClicked: {
                            copyPasswordDialog.close()
                        }

                        background: Rectangle {
                            radius: 9
                            color: "#252C3A"
                        }

                        contentItem: Text {
                            text: "إلغاء"
                            color: "white"
                            font.pixelSize: 13
                            font.bold: true
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }
                }
            }
        }

        MouseArea {
            id: mouseArea

            anchors.fill: parent

            hoverEnabled: true

            cursorShape: Qt.PointingHandCursor

            acceptedButtons: Qt.NoButton
        }
    }
}
