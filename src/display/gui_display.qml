import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Rectangle {
    id: root
    color: "#eef1f5"

    signal manualButtonPressed()
    signal manualButtonReleased()
    signal autoButtonClicked()
    signal abortButtonClicked()
    signal modeButtonClicked()
    signal sendButtonClicked(string text)
    signal settingsButtonClicked()
    signal titleMinimize()
    signal titleClose()
    signal titleDragStart(real mouseX, real mouseY)
    signal titleDragMoveTo(real mouseX, real mouseY)
    signal titleDragEnd()

    readonly property string statusText: displayModel ? displayModel.statusText : "\u72b6\u6001\uff1a\u672a\u8fde\u63a5"
    readonly property bool autoMode: displayModel ? displayModel.autoMode : false
    readonly property bool busyState: isBusyStatus(statusText)
    readonly property color accentColor: statusAccent(statusText)

    function isBusyStatus(text) {
        var value = (text || "").toLowerCase()
        return value.indexOf("\u8046\u542c") !== -1
            || value.indexOf("\u8bc6\u522b") !== -1
            || value.indexOf("\u601d\u8003") !== -1
            || value.indexOf("\u64ad\u653e") !== -1
            || value.indexOf("listening") !== -1
            || value.indexOf("speaking") !== -1
            || value.indexOf("thinking") !== -1
    }

    function statusAccent(text) {
        var value = (text || "").toLowerCase()
        if (value.indexOf("\u9519\u8bef") !== -1 || value.indexOf("\u5931\u8d25") !== -1 || value.indexOf("\u65ad\u5f00") !== -1 || value.indexOf("error") !== -1) {
            return "#e5484d"
        }
        if (value.indexOf("\u672a\u8fde\u63a5") !== -1 || value.indexOf("offline") !== -1) {
            return "#697386"
        }
        if (value.indexOf("\u64ad\u653e") !== -1 || value.indexOf("speaking") !== -1) {
            return "#7c3aed"
        }
        if (value.indexOf("\u601d\u8003") !== -1 || value.indexOf("\u8bc6\u522b") !== -1 || value.indexOf("thinking") !== -1) {
            return "#d97706"
        }
        if (value.indexOf("\u8046\u542c") !== -1 || value.indexOf("listening") !== -1) {
            return "#2563eb"
        }
        if (value.indexOf("\u8fde\u63a5") !== -1 || value.indexOf("connected") !== -1 || value.indexOf("\u5f85\u547d") !== -1) {
            return "#0f9f6e"
        }
        return "#2563eb"
    }

    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: "#f8fafc" }
            GradientStop { position: 1.0; color: "#e8edf3" }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        Rectangle {
            id: titleBar
            Layout.fillWidth: true
            Layout.preferredHeight: 38
            color: "#f8fafc"

            MouseArea {
                anchors.fill: parent
                acceptedButtons: Qt.LeftButton
                onPressed: root.titleDragStart(mouse.x, mouse.y)
                onPositionChanged: if (pressed) root.titleDragMoveTo(mouse.x, mouse.y)
                onReleased: root.titleDragEnd()
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 14
                anchors.rightMargin: 8
                spacing: 8

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    Rectangle {
                        width: 9
                        height: 9
                        radius: 5
                        color: root.accentColor
                    }

                    Text {
                        text: "xiaokang"
                        color: "#1f2937"
                        font.family: "Microsoft YaHei UI"
                        font.pixelSize: 13
                        font.weight: Font.DemiBold
                    }
                }

                Rectangle {
                    width: 28
                    height: 28
                    radius: 7
                    color: minMouse.pressed ? "#dbe1ea" : (minMouse.containsMouse ? "#edf1f6" : "transparent")

                    Text {
                        anchors.centerIn: parent
                        text: "-"
                        color: "#526071"
                        font.pixelSize: 18
                    }

                    MouseArea {
                        id: minMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        onClicked: root.titleMinimize()
                    }
                }

                Rectangle {
                    width: 28
                    height: 28
                    radius: 7
                    color: closeMouse.pressed ? "#dc2626" : (closeMouse.containsMouse ? "#ef4444" : "transparent")

                    Text {
                        anchors.centerIn: parent
                        text: "x"
                        color: closeMouse.containsMouse ? "white" : "#697386"
                        font.pixelSize: 15
                    }

                    MouseArea {
                        id: closeMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        onClicked: root.titleClose()
                    }
                }
            }
        }

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 16
                spacing: 14

                Rectangle {
                    id: statusPanel
                    Layout.fillWidth: true
                    Layout.preferredHeight: 58
                    radius: 8
                    color: "#ffffff"
                    border.color: "#e2e8f0"
                    border.width: 1

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 18
                        anchors.rightMargin: 18
                        spacing: 12

                        Rectangle {
                            width: 13
                            height: 13
                            radius: 7
                            color: root.accentColor
                            opacity: root.busyState ? 0.95 : 0.75

                            SequentialAnimation on opacity {
                                running: root.busyState
                                loops: Animation.Infinite
                                NumberAnimation { to: 0.35; duration: 720; easing.type: Easing.InOutQuad }
                                NumberAnimation { to: 0.95; duration: 720; easing.type: Easing.InOutQuad }
                            }
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 2

                            Text {
                                Layout.fillWidth: true
                                text: root.statusText
                                color: "#111827"
                                font.family: "Microsoft YaHei UI"
                                font.pixelSize: 15
                                font.weight: Font.DemiBold
                                elide: Text.ElideRight
                            }

                            Text {
                                Layout.fillWidth: true
                                text: root.autoMode ? "\u81ea\u52a8\u5bf9\u8bdd\u6a21\u5f0f" : "\u624b\u52a8\u6309\u4f4f\u8bf4\u8bdd"
                                color: "#697386"
                                font.family: "Microsoft YaHei UI"
                                font.pixelSize: 12
                                elide: Text.ElideRight
                            }
                        }

                        Rectangle {
                            width: 84
                            height: 28
                            radius: 14
                            color: Qt.rgba(root.accentColor.r, root.accentColor.g, root.accentColor.b, 0.12)

                            Text {
                                anchors.centerIn: parent
                                text: root.busyState ? "\u5904\u7406\u4e2d" : "\u5c31\u7eea"
                                color: root.accentColor
                                font.family: "Microsoft YaHei UI"
                                font.pixelSize: 12
                                font.weight: Font.DemiBold
                            }
                        }
                    }
                }

                Item {
                    id: stage
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.minimumHeight: 130

                    Rectangle {
                        id: pulseOuter
                        anchors.centerIn: parent
                        width: Math.min(parent.width, parent.height) * 0.78
                        height: width
                        radius: width / 2
                        color: "transparent"
                        border.width: 1
                        border.color: Qt.rgba(root.accentColor.r, root.accentColor.g, root.accentColor.b, 0.22)
                        opacity: root.busyState ? 0.8 : 0.38

                        SequentialAnimation on scale {
                            running: root.busyState
                            loops: Animation.Infinite
                            NumberAnimation { to: 1.045; duration: 900; easing.type: Easing.InOutQuad }
                            NumberAnimation { to: 1.0; duration: 900; easing.type: Easing.InOutQuad }
                        }
                    }

                    Row {
                        id: wave
                        anchors.horizontalCenter: parent.horizontalCenter
                        anchors.bottom: emotionFrame.top
                        anchors.bottomMargin: 14
                        spacing: 5
                        opacity: root.busyState ? 1.0 : 0.42

                        Repeater {
                            model: 7

                            Rectangle {
                                width: 5
                                height: 16 + ((index % 4) * 7)
                                radius: 3
                                color: root.accentColor
                                opacity: 0.72
                                anchors.verticalCenter: parent.verticalCenter

                                SequentialAnimation on height {
                                    running: root.busyState
                                    loops: Animation.Infinite
                                    PauseAnimation { duration: index * 70 }
                                    NumberAnimation { to: 42 - ((index % 3) * 6); duration: 360; easing.type: Easing.InOutSine }
                                    NumberAnimation { to: 14 + ((index % 4) * 7); duration: 420; easing.type: Easing.InOutSine }
                                }
                            }
                        }
                    }

                    Rectangle {
                        id: emotionFrame
                        anchors.centerIn: parent
                        width: Math.max(120, Math.min(parent.width, parent.height) * 0.48)
                        height: width
                        radius: width / 2
                        color: "#ffffff"
                        border.color: Qt.rgba(root.accentColor.r, root.accentColor.g, root.accentColor.b, 0.22)
                        border.width: 1

                        Loader {
                            id: emotionLoader
                            anchors.centerIn: parent
                            width: parent.width * 0.72
                            height: parent.height * 0.72

                            sourceComponent: {
                                var path = displayModel ? displayModel.emotionPath : ""
                                if (!path || path.length === 0) return emojiComponent
                                if (path.indexOf(".gif") !== -1) return gifComponent
                                if (path.indexOf(".") !== -1) return imageComponent
                                return emojiComponent
                            }

                            Component {
                                id: gifComponent
                                AnimatedImage {
                                    source: displayModel ? displayModel.emotionPath : ""
                                    fillMode: Image.PreserveAspectFit
                                    playing: true
                                    speed: 1.05
                                    cache: true
                                }
                            }

                            Component {
                                id: imageComponent
                                Image {
                                    source: displayModel ? displayModel.emotionPath : ""
                                    fillMode: Image.PreserveAspectFit
                                    cache: true
                                }
                            }

                            Component {
                                id: emojiComponent
                                Text {
                                    text: displayModel ? displayModel.emotionPath : "AI"
                                    color: "#111827"
                                    font.pixelSize: 70
                                    font.weight: Font.Bold
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                }
                            }
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 78
                    radius: 8
                    color: "#ffffff"
                    border.color: "#e2e8f0"
                    border.width: 1

                    Text {
                        anchors.fill: parent
                        anchors.margins: 14
                        text: displayModel ? displayModel.ttsText : "\u7b49\u5f85\u5bf9\u8bdd"
                        color: "#334155"
                        font.family: "Microsoft YaHei UI"
                        font.pixelSize: 14
                        lineHeight: 1.15
                        wrapMode: Text.WordWrap
                        maximumLineCount: 3
                        elide: Text.ElideRight
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 84
            color: "#f8fafc"
            border.color: "#e2e8f0"
            border.width: 1

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 14
                anchors.rightMargin: 14
                spacing: 8

                Button {
                    id: talkBtn
                    Layout.preferredWidth: 132
                    Layout.maximumWidth: 172
                    Layout.fillWidth: true
                    Layout.preferredHeight: 42
                    text: root.autoMode ? (displayModel ? displayModel.buttonText : "\u5f00\u59cb\u5bf9\u8bdd") : "\u6309\u4f4f\u8bf4\u8bdd"

                    background: Rectangle {
                        radius: 8
                        color: talkBtn.pressed ? "#1d4ed8" : (talkBtn.hovered ? "#2563eb" : root.accentColor)
                    }

                    contentItem: Text {
                        text: talkBtn.text
                        color: "white"
                        font.family: "Microsoft YaHei UI"
                        font.pixelSize: 13
                        font.weight: Font.DemiBold
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                    }

                    onPressed: if (!root.autoMode) root.manualButtonPressed()
                    onReleased: if (!root.autoMode) root.manualButtonReleased()
                    onClicked: if (root.autoMode) root.autoButtonClicked()
                }

                Button {
                    id: abortBtn
                    Layout.preferredWidth: 82
                    Layout.maximumWidth: 104
                    Layout.preferredHeight: 42
                    text: "\u4e2d\u65ad"

                    background: Rectangle {
                        radius: 8
                        color: abortBtn.pressed ? "#fee2e2" : (abortBtn.hovered ? "#fff1f2" : "#ffffff")
                        border.color: root.busyState ? "#fca5a5" : "#d9e0ea"
                        border.width: 1
                    }

                    contentItem: Text {
                        text: abortBtn.text
                        color: root.busyState ? "#dc2626" : "#334155"
                        font.family: "Microsoft YaHei UI"
                        font.pixelSize: 13
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }

                    onClicked: root.abortButtonClicked()
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 130
                    Layout.preferredHeight: 42
                    radius: 8
                    color: "#ffffff"
                    border.color: textInput.activeFocus ? root.accentColor : "#d9e0ea"
                    border.width: 1

                    TextInput {
                        id: textInput
                        anchors.fill: parent
                        anchors.leftMargin: 12
                        anchors.rightMargin: 12
                        verticalAlignment: TextInput.AlignVCenter
                        font.family: "Microsoft YaHei UI"
                        font.pixelSize: 13
                        color: "#111827"
                        selectByMouse: true
                        clip: true

                        Text {
                            anchors.fill: parent
                            text: "\u8f93\u5165\u6587\u5b57\u6d88\u606f..."
                            font: textInput.font
                            color: "#9aa4b2"
                            verticalAlignment: Text.AlignVCenter
                            visible: !textInput.text && !textInput.activeFocus
                        }

                        Keys.onReturnPressed: {
                            if (textInput.text.trim().length > 0) {
                                root.sendButtonClicked(textInput.text)
                                textInput.text = ""
                            }
                        }
                    }
                }

                Button {
                    id: sendBtn
                    Layout.preferredWidth: 66
                    Layout.maximumWidth: 76
                    Layout.preferredHeight: 42
                    text: "\u53d1\u9001"

                    background: Rectangle {
                        radius: 8
                        color: sendBtn.pressed ? "#1d4ed8" : (sendBtn.hovered ? "#2563eb" : "#1f2937")
                    }

                    contentItem: Text {
                        text: sendBtn.text
                        color: "white"
                        font.family: "Microsoft YaHei UI"
                        font.pixelSize: 13
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }

                    onClicked: {
                        if (textInput.text.trim().length > 0) {
                            root.sendButtonClicked(textInput.text)
                            textInput.text = ""
                        }
                    }
                }

                Button {
                    id: modeBtn
                    Layout.preferredWidth: 92
                    Layout.maximumWidth: 112
                    Layout.preferredHeight: 42
                    text: root.autoMode ? "\u81ea\u52a8\u6a21\u5f0f" : "\u624b\u52a8\u6a21\u5f0f"

                    background: Rectangle {
                        radius: 8
                        color: modeBtn.pressed ? "#e2e8f0" : (modeBtn.hovered ? "#edf2f7" : "#ffffff")
                        border.color: root.autoMode ? root.accentColor : "#d9e0ea"
                        border.width: 1
                    }

                    contentItem: Text {
                        text: modeBtn.text
                        color: root.autoMode ? root.accentColor : "#334155"
                        font.family: "Microsoft YaHei UI"
                        font.pixelSize: 13
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                    }

                    onClicked: root.modeButtonClicked()
                }

                Button {
                    id: settingsBtn
                    Layout.preferredWidth: 52
                    Layout.maximumWidth: 56
                    Layout.preferredHeight: 42
                    text: "\u8bbe\u7f6e"

                    background: Rectangle {
                        radius: 8
                        color: settingsBtn.pressed ? "#e2e8f0" : (settingsBtn.hovered ? "#edf2f7" : "#ffffff")
                        border.color: "#d9e0ea"
                        border.width: 1
                    }

                    contentItem: Text {
                        text: settingsBtn.text
                        color: "#334155"
                        font.family: "Microsoft YaHei UI"
                        font.pixelSize: 13
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }

                    onClicked: root.settingsButtonClicked()
                }
            }
        }
    }
}
