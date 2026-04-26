# -*- coding: utf-8 -*-
"""Data model used by the QML main window."""

from PyQt5.QtCore import QObject, pyqtProperty, pyqtSignal


class GuiDisplayModel(QObject):
    """Bridge display state from Python to QML."""

    statusTextChanged = pyqtSignal()
    emotionPathChanged = pyqtSignal()
    ttsTextChanged = pyqtSignal()
    buttonTextChanged = pyqtSignal()
    modeTextChanged = pyqtSignal()
    autoModeChanged = pyqtSignal()

    manualButtonPressed = pyqtSignal()
    manualButtonReleased = pyqtSignal()
    autoButtonClicked = pyqtSignal()
    abortButtonClicked = pyqtSignal()
    modeButtonClicked = pyqtSignal()
    sendButtonClicked = pyqtSignal(str)
    settingsButtonClicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._status_text = "\u72b6\u6001\uff1a\u672a\u8fde\u63a5"
        self._emotion_path = ""
        self._tts_text = "\u7b49\u5f85\u5bf9\u8bdd"
        self._button_text = "\u5f00\u59cb\u5bf9\u8bdd"
        self._mode_text = "\u624b\u52a8\u6a21\u5f0f"
        self._auto_mode = False
        self._is_connected = False

    @pyqtProperty(str, notify=statusTextChanged)
    def statusText(self):
        return self._status_text

    @statusText.setter
    def statusText(self, value):
        if self._status_text != value:
            self._status_text = value
            self.statusTextChanged.emit()

    @pyqtProperty(str, notify=emotionPathChanged)
    def emotionPath(self):
        return self._emotion_path

    @emotionPath.setter
    def emotionPath(self, value):
        if self._emotion_path != value:
            self._emotion_path = value
            self.emotionPathChanged.emit()

    @pyqtProperty(str, notify=ttsTextChanged)
    def ttsText(self):
        return self._tts_text

    @ttsText.setter
    def ttsText(self, value):
        if self._tts_text != value:
            self._tts_text = value
            self.ttsTextChanged.emit()

    @pyqtProperty(str, notify=buttonTextChanged)
    def buttonText(self):
        return self._button_text

    @buttonText.setter
    def buttonText(self, value):
        if self._button_text != value:
            self._button_text = value
            self.buttonTextChanged.emit()

    @pyqtProperty(str, notify=modeTextChanged)
    def modeText(self):
        return self._mode_text

    @modeText.setter
    def modeText(self, value):
        if self._mode_text != value:
            self._mode_text = value
            self.modeTextChanged.emit()

    @pyqtProperty(bool, notify=autoModeChanged)
    def autoMode(self):
        return self._auto_mode

    @autoMode.setter
    def autoMode(self, value):
        if self._auto_mode != value:
            self._auto_mode = value
            self.autoModeChanged.emit()

    def update_status(self, status: str, connected: bool):
        self.statusText = f"\u72b6\u6001\uff1a{status}"
        self._is_connected = connected

    def update_text(self, text: str):
        self.ttsText = text or "\u7b49\u5f85\u5bf9\u8bdd"

    def update_emotion(self, emotion_path: str):
        self.emotionPath = emotion_path

    def update_button_text(self, text: str):
        self.buttonText = text or "\u5f00\u59cb\u5bf9\u8bdd"

    def update_mode_text(self, text: str):
        self.modeText = text

    def set_auto_mode(self, is_auto: bool):
        self.autoMode = is_auto
        self.modeText = (
            "\u81ea\u52a8\u6a21\u5f0f" if is_auto else "\u624b\u52a8\u6a21\u5f0f"
        )
