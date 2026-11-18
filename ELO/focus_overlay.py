"""Tela de câmera ampliada com janelas PiP móveis e redimensionáveis."""

from PySide6.QtCore import Qt, Signal, QEvent
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


class PiPPanel(QFrame):
    """Janela flutuante interna que pode ser arrastada e redimensionada."""

    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setObjectName("pipPanel")
        self.setMinimumSize(300, 180)
        self.setStyleSheet(
            "QFrame#pipPanel { background:#FFFFFF; border:1px solid #B8CBD6; "
            "border-radius:12px; }"
        )
        self._drag_start = None
        self._move_start = None
        self._resize_start = None
        self._size_start = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 7, 8, 8)
        outer.setSpacing(5)
        self.header = QFrame(self)
        self.header.setStyleSheet("background:#EAF3F7; border-radius:7px;")
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(8, 4, 5, 4)
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-weight:700; color:#214D6C; background:transparent;")
        header_layout.addWidget(self.title_label, 1)
        self.hide_button = QPushButton("×")
        self.hide_button.setFixedSize(26, 26)
        self.hide_button.setToolTip("Ocultar esta janela PiP")
        self.hide_button.clicked.connect(self.hide)
        header_layout.addWidget(self.hide_button)
        outer.addWidget(self.header)

        self.content_host = QWidget(self)
        self.content_layout = QVBoxLayout(self.content_host)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)
        outer.addWidget(self.content_host, 1)

        self.resize_grip = QLabel("◢", self)
        self.resize_grip.setAlignment(Qt.AlignRight | Qt.AlignBottom)
        self.resize_grip.setStyleSheet("color:#668397; background:transparent; padding:0 2px;")
        self.resize_grip.setFixedHeight(14)
        outer.addWidget(self.resize_grip)

        self.header.installEventFilter(self)
        self.title_label.installEventFilter(self)
        self.resize_grip.installEventFilter(self)

    def set_content(self, widget):
        if self.content_layout.count():
            self.take_content()
        widget.setParent(self.content_host)
        self.content_layout.addWidget(widget)

    def set_title(self, title):
        self.title_label.setText(title)

    def take_content(self):
        if not self.content_layout.count():
            return None
        item = self.content_layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.setParent(None)
        return widget

    def eventFilter(self, watched, event):
        event_type = event.type()
        global_pos = event.globalPosition().toPoint() if hasattr(event, "globalPosition") else None
        if watched in (self.header, self.title_label):
            if event_type == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                self._drag_start = global_pos
                self._move_start = self.pos()
                return True
            if event_type == QEvent.MouseMove and self._drag_start is not None:
                delta = global_pos - self._drag_start
                self.move(self._clamped_position(self._move_start + delta))
                return True
            if event_type == QEvent.MouseButtonRelease:
                self._drag_start = None
                return True
        if watched is self.resize_grip:
            if event_type == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                self._resize_start = global_pos
                self._size_start = self.size()
                return True
            if event_type == QEvent.MouseMove and self._resize_start is not None:
                delta = global_pos - self._resize_start
                max_width = max(self.minimumWidth(), self.parentWidget().width() - self.x())
                max_height = max(self.minimumHeight(), self.parentWidget().height() - self.y())
                self.resize(
                    min(max_width, max(self.minimumWidth(), self._size_start.width() + delta.x())),
                    min(max_height, max(self.minimumHeight(), self._size_start.height() + delta.y())),
                )
                return True
            if event_type == QEvent.MouseButtonRelease:
                self._resize_start = None
                return True
        return super().eventFilter(watched, event)

    def _clamped_position(self, position):
        parent = self.parentWidget()
        if parent is None:
            return position
        return position.__class__(
            max(0, min(position.x(), parent.width() - self.width())),
            max(0, min(position.y(), parent.height() - self.height())),
        )


class CameraFocusOverlay(QWidget):
    """Ocupa a janela inteira e mantém câmera, outra câmera e robôs em PiP."""

    exitRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("cameraFocusOverlay")
        self.setStyleSheet("QWidget#cameraFocusOverlay { background:#101E28; }")
        self.setFocusPolicy(Qt.StrongFocus)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        toolbar = QFrame(self)
        toolbar.setStyleSheet("background:#102C3D;")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(14, 8, 14, 8)
        self.back_button = QPushButton("←  Voltar ao monitoramento")
        self.back_button.clicked.connect(self.exitRequested)
        toolbar_layout.addWidget(self.back_button)
        self.heading = QLabel("Câmera ampliada")
        self.heading.setStyleSheet("color:white; font-size:16px; font-weight:700; background:transparent;")
        toolbar_layout.addWidget(self.heading, 1)
        hint = QLabel("Arraste e redimensione as janelas PiP")
        hint.setStyleSheet("color:#C5D7E0; background:transparent;")
        toolbar_layout.addWidget(hint)
        layout.addWidget(toolbar)

        self.canvas = QWidget(self)
        self.canvas.setStyleSheet("background:#101E28;")
        layout.addWidget(self.canvas, 1)

        self.main_host = QFrame(self.canvas)
        self.main_host.setStyleSheet("background:#101E28; border:0;")
        self.main_layout = QVBoxLayout(self.main_host)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.camera_pip = PiPPanel("Outra câmera", self.canvas)
        self.robot_pip = PiPPanel("Modelos 3D dos robôs", self.canvas)
        self.camera_pip.resize(370, 260)
        self.robot_pip.resize(370, 350)

    def set_main_widget(self, widget):
        if self.main_layout.count():
            self.take_main_widget()
        widget.setParent(self.main_host)
        self.main_layout.addWidget(widget)

    def take_main_widget(self):
        if not self.main_layout.count():
            return None
        item = self.main_layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.setParent(None)
        return widget

    def set_camera_pip(self, widget):
        self.camera_pip.set_content(widget)

    def take_camera_pip(self):
        return self.camera_pip.take_content()

    def set_robot_pip(self, widget):
        self.robot_pip.set_content(widget)

    def take_robot_pip(self):
        return self.robot_pip.take_content()

    def set_camera_title(self, title, pip_title):
        self.heading.setText(title)
        self.camera_pip.set_title(pip_title)

    def place_pips(self):
        width = self.canvas.width()
        height = self.canvas.height()
        pip_width = min(370, max(310, width - 30))
        x = max(10, width - pip_width - 18)
        self.camera_pip.resize(pip_width, min(260, max(220, height // 2 - 12)))
        self.robot_pip.resize(pip_width, min(350, max(300, height // 2 - 12)))
        self.camera_pip.move(x, 14)
        self.robot_pip.move(x, min(height - self.robot_pip.height() - 12, self.camera_pip.height() + 26))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.main_host.setGeometry(0, 0, self.canvas.width(), self.canvas.height())
        self.place_pips()

    def showEvent(self, event):
        super().showEvent(event)
        self.setFocus()
        self.place_pips()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.exitRequested.emit()
            event.accept()
            return
        super().keyPressEvent(event)
